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
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from spinn_utilities.config_holder import get_report_path
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from pacman.model.graphs import AbstractVertex
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import MultiRegionSDRAM, ConstantSDRAM
from pacman.model.placements import Placement
from spinn_front_end_common.abstract_models import (
    AbstractRewritesDataSpecification, AbstractGeneratesDataSpecification)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import (
    ConfigurationException, DataSpecException)
from spinn_front_end_common.interface.ds import (
    DataSpecificationGenerator, DsSqlliteDatabase)
from spinn_front_end_common.utilities.utility_calls import get_report_writer

logger = FormatAdapter(logging.getLogger(__name__))


def graph_data_specification_writer(
        placement_order: Optional[Sequence[Placement]] = None) -> str:
    """
    :param placement_order:
        the optional order in which placements should be examined
    :return: Path to DSG targets database
    :raises ConfigurationException:
        If the DSG asks to use more SDRAM than is available.
    """
    return _GraphDataSpecificationWriter().run(placement_order)


class _GraphDataSpecificationWriter(object):
    """
    Executes the data specification generation step.
    """

    __slots__ = (
        # Dict of SDRAM usage by chip coordinates
        "_sdram_usage",
        # Dict of list of vertices by chip coordinates
        "_vertices_by_chip")

    def __init__(self) -> None:
        self._sdram_usage: Dict[Tuple[int, int], int] = defaultdict(lambda: 0)
        self._vertices_by_chip: \
            Dict[Tuple[int, int], List[AbstractGeneratesDataSpecification]] =\
            defaultdict(list)

    def run(self,
            placement_order: Optional[Sequence[Placement]] = None) -> str:
        """
        :param placement_order:
            the optional order in which placements should be examined
        :return: Path to DSG targets database
        :raises ConfigurationException:
            If the DSG asks to use more SDRAM than is available.
        """
        # iterate though vertices and call generate_data_spec for each
        # vertex
        path = get_report_path("path_dataspec_database")
        with DsSqlliteDatabase(path) as ds_db:
            ds_db.write_session_credentials_to_db()
            ds_db.set_info()

            placements: Iterable[Placement]
            if placement_order is None:
                placements = FecDataView.iterate_placemements()
                n_placements = FecDataView.get_n_placements()
            else:
                placements = placement_order
                n_placements = len(placement_order)

            progress = ProgressBar(n_placements,
                                   "Generating data specifications")
            vertices_to_reset: List[AbstractRewritesDataSpecification] = list()

            for placement in progress.over(placements):
                # Try to generate the data spec for the placement
                vertex = placement.vertex
                generated = self.__generate_data_spec_for_vertices(
                    placement, vertex, ds_db)

                if generated and isinstance(
                        vertex, AbstractRewritesDataSpecification):
                    vertices_to_reset.append(vertex)

            # Ensure that the vertices know their regions have been reloaded
            for rewriter in vertices_to_reset:
                rewriter.set_reload_required(False)

            self._run_check_queries(ds_db)

        return path

    def __generate_data_spec_for_vertices(
            self, placement: Placement, vertex: AbstractVertex,
            ds_db: DsSqlliteDatabase) -> bool:
        """
        :param placement: placement of machine graph to cores
        :param vertex: the specific vertex to write DSG for.
        :param ds_db:
        :return: True if the vertex was data spec-able, False otherwise
        :raises ConfigurationException: if things don't fit
        """
        # if the vertex can generate a DSG, call it
        if not isinstance(vertex, AbstractGeneratesDataSpecification):
            return False

        x = placement.x
        y = placement.y
        p = placement.p

        report_writer = get_report_writer(x, y, p)
        spec = DataSpecificationGenerator(
            x, y, p, vertex, ds_db, report_writer)

        # generate the DSG file
        vertex.generate_data_specification(spec, placement)

        # Check the memory usage
        total_size = ds_db.get_total_regions_size(x, y, p)
        total_est_size = 0

        # Check per-region memory usage if possible
        if isinstance(vertex, MachineVertex):
            sdram = vertex.sdram_required
            if isinstance(sdram, MultiRegionSDRAM):
                region_sizes = ds_db.get_region_sizes(x, y, p)
                for i, size in region_sizes.items():
                    est_size = sdram.regions.get(i, ConstantSDRAM(0))
                    est_size = est_size.get_total_sdram(
                        FecDataView.get_max_run_time_steps())
                    total_est_size += est_size
                    if size > est_size:
                        raise ValueError(
                            f"Region {i} of vertex {vertex.label} is bigger"
                            f" than expected: {est_size} estimated vs. {size}"
                            " actual")
            else:
                total_est_size = sdram.get_total_sdram(
                    FecDataView.get_max_run_time_steps())

            if total_size > total_est_size:
                raise ValueError(
                    f"Data of vertex {vertex.label} is bigger than expected:"
                    f" estimated: {total_est_size} vs. actual: {total_size}")

        self._vertices_by_chip[x, y].append(vertex)
        self._sdram_usage[x, y] += total_size
        if (self._sdram_usage[x, y] <=
                FecDataView().get_chip_at(x, y).sdram):
            return True

        # creating the error message which contains the memory usage of
        # what each core within the chip uses and its original estimate.
        ts = FecDataView.get_max_run_time_steps()
        memory_usage = "\n".join(
            f"    {vert}: {vert.sdram_required.get_total_sdram(ts)}"
            for vert in self._vertices_by_chip[x, y])

        raise ConfigurationException(
            f"Too much SDRAM has been used on {x}, {y}.  Vertices and"
            f" their usage on that chip is as follows:\n{memory_usage}")

    def _run_check_queries(self, ds_db: DsSqlliteDatabase) -> None:
        msg = ""
        for x, y, p, region, reference, lbl in ds_db.get_unlinked_references():
            if lbl is None:
                label = ""
            else:
                label = f"({lbl})"
            msg += f"core {x}:{y}:{p} has a broken reference " \
                f"{reference}{label} from region {region} "

        for x, y, p, region in ds_db.get_double_region():
            msg += f"core {x}:{y}:{p} {region} " \
                "has both a region reserve and a reference "

        if msg != "":
            raise DataSpecException(msg)
