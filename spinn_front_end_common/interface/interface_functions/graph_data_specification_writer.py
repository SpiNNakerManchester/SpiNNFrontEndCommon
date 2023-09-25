# Copyright (c) 2016 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import defaultdict
import logging
import os

from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from pacman.model.resources import MultiRegionSDRAM, ConstantSDRAM
from spinn_front_end_common.abstract_models import (
    AbstractRewritesDataSpecification, AbstractGeneratesDataSpecification)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import APP_PTR_TABLE_BYTE_SIZE
from spinn_front_end_common.utilities.exceptions import (
    ConfigurationException, DataSpecException)
from spinn_front_end_common.interface.ds import (
    DataSpecificationGenerator, DsSqlliteDatabase)
from spinn_front_end_common.utilities.utility_calls import get_report_writer

logger = FormatAdapter(logging.getLogger(__name__))


def graph_data_specification_writer(placement_order=None):
    """
    :param list(~pacman.model.placements.Placement) placement_order:
        the optional order in which placements should be examined
    :return: Path to DSG targets database
    :rtype: str
    :raises ConfigurationException:
        If the DSG asks to use more SDRAM than is available.
    """
    writer = _GraphDataSpecificationWriter()
    return writer.run(placement_order)


class _GraphDataSpecificationWriter(object):
    """
    Executes the data specification generation step.
    """

    __slots__ = (
        # Dict of SDRAM usage by chip coordinates
        "_sdram_usage",
        # Dict of list of vertices by chip coordinates
        "_vertices_by_chip")

    def __init__(self):
        self._sdram_usage = defaultdict(lambda: 0)
        self._vertices_by_chip = defaultdict(list)

    def run(self, placement_order=None):
        """
        :param list(~pacman.model.placements.Placement) placement_order:
            the optional order in which placements should be examined
        :return: Path to DSG targets database
        :rtype: str
        :raises ConfigurationException:
            If the DSG asks to use more SDRAM than is available.
        """
        # iterate though vertices and call generate_data_spec for each
        # vertex
        path = os.path.join(FecDataView.get_run_dir_path(),
                            f"ds{FecDataView.get_reset_str()}.sqlite3")
        with DsSqlliteDatabase(path) as ds_db:
            ds_db.write_session_credentials_to_db()
            ds_db. set_app_id()

            if placement_order is None:
                placement_order = FecDataView.iterate_placemements()
                n_placements = FecDataView.get_n_placements()
            else:
                n_placements = len(placement_order)

            progress = ProgressBar(
                n_placements, "Generating data specifications")
            vertices_to_reset = list()

            for placement in progress.over(placement_order):
                # Try to generate the data spec for the placement
                vertex = placement.vertex
                generated = self.__generate_data_spec_for_vertices(
                    placement, vertex, ds_db)

                if generated and isinstance(
                        vertex, AbstractRewritesDataSpecification):
                    vertices_to_reset.append(vertex)

                # If the spec wasn't generated directly, and there is an
                # application vertex, try with that
                if not generated and vertex.app_vertex is not None:
                    generated = self.__generate_data_spec_for_vertices(
                        placement, vertex.app_vertex, ds_db)
                    if generated and isinstance(
                            vertex.app_vertex,
                            AbstractRewritesDataSpecification):
                        vertices_to_reset.append(vertex.app_vertex)

            # Ensure that the vertices know their regions have been reloaded
            for vertex in vertices_to_reset:
                vertex.set_reload_required(False)

            self._run_check_queries(ds_db)
        return path

    def __generate_data_spec_for_vertices(self, pl, vertex, ds_db):
        """
        :param ~.Placement pl: placement of machine graph to cores
        :param ~.AbstractVertex vertex: the specific vertex to write DSG for.
        :param DsSqlliteDatabase ds_db:
        :return: True if the vertex was data spec-able, False otherwise
        :rtype: bool
        :raises ConfigurationException: if things don't fit
        """
        # if the vertex can generate a DSG, call it
        if not isinstance(vertex, AbstractGeneratesDataSpecification):
            return False

        x = pl.x
        y = pl.y
        p = pl.p

        report_writer = get_report_writer(x, y, p)
        spec = DataSpecificationGenerator(
            x, y, p, vertex, ds_db, report_writer)

        # generate the DSG file
        vertex.generate_data_specification(spec, pl)

        # Check the memory usage
        total_size = ds_db.get_total_regions_size(x, y, p)
        region_size = APP_PTR_TABLE_BYTE_SIZE + total_size

        # Check per-region memory usage if possible
        sdram = vertex.sdram_required
        if isinstance(sdram, MultiRegionSDRAM):
            region_sizes = ds_db.get_region_sizes(x, y, p)
            for i, size in region_sizes.items():
                est_size = sdram.regions.get(i, ConstantSDRAM(0))
                est_size = est_size.get_total_sdram(
                    FecDataView.get_max_run_time_steps())
                if size > est_size:
                    # pylint: disable=logging-too-many-args
                    logger.warning(
                        "Region {} of vertex {} is bigger than expected: "
                        "{} estimated vs. {} actual",
                        i, vertex.label, est_size, size)

        self._vertices_by_chip[x, y].append(vertex)
        self._sdram_usage[x, y] += total_size
        if (self._sdram_usage[x, y] <=
                FecDataView().get_chip_at(x, y).sdram):
            return True

        # creating the error message which contains the memory usage of
        # what each core within the chip uses and its original estimate.
        memory_usage = "\n".join(
            "    {}: {} (total={}, estimated={})".format(
                vert, region_size, sum(region_size),
                vert.sdram_required.get_total_sdram(
                    FecDataView.get_max_run_time_steps()))
            for vert in self._vertices_by_chip[x, y])

        raise ConfigurationException(
            f"Too much SDRAM has been used on {x}, {y}.  Vertices and"
            f" their usage on that chip is as follows:\n{memory_usage}")

    def _run_check_queries(self, ds_db):
        msg = ""
        for bad in ds_db.get_unlinked_references():
            x, y, p, region, reference, label = bad
            if label is None:
                label = ""
            else:
                label = f"({label})"
            msg = f"{msg}core {x}:{y}:{p} has a broken reference " \
                  f"{reference}{label} from region {region} "

        for bad in ds_db.get_double_region():
            x, y, p, region = bad
            msg = f"{msg}core {x}:{y}:{p} {region} " \
                  f"has both a region reserve and a reference "

        if msg != "":
            raise DataSpecException(msg)
