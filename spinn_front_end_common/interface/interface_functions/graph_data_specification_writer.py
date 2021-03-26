# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from collections import defaultdict

from data_specification.constants import APP_PTR_TABLE_BYTE_SIZE
from spinn_utilities.progress_bar import ProgressBar
from data_specification import DataSpecificationGenerator
from data_specification.utility_calls import get_report_writer
from spinn_front_end_common.abstract_models import (
    AbstractRewritesDataSpecification, AbstractGeneratesDataSpecification)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.interface.ds.data_specification_targets import (
    DataSpecificationTargets)


class GraphDataSpecificationWriter(object):
    """ Executes the data specification generation step.
    """

    __slots__ = (
        # Dict of SDRAM usage by chip coordinates
        "_sdram_usage",
        # Dict of list of region sizes by core coordinates
        "_region_sizes",
        # Dict of list of vertices by chip coordinates
        "_vertices_by_chip",
        # spinnmachine instance
        "_machine",
        # hostname
        "_hostname",
        # directory where reports go
        "_report_dir",
        # bool for writing texts
        "_write_text",
    )

    def __init__(self):
        self._sdram_usage = defaultdict(lambda: 0)
        self._region_sizes = dict()
        self._vertices_by_chip = defaultdict(list)

    def __call__(
            self, placements, hostname,
            report_default_directory, write_text_specs,
            machine, data_n_timesteps, placement_order=None):
        """
        :param ~pacman.model.placements.Placements placements:
            placements of machine graph to cores
        :param str hostname: SpiNNaker machine name
        :param str report_default_directory:
            the location where reports are stored
        :param bool write_text_specs:
            True if the textual version of the specification is to be written
        :param ~spinn_machine.Machine machine:
            the python representation of the SpiNNaker machine
        :param int data_n_timesteps:
            The number of timesteps for which data space will been reserved
        :param list(~pacman.model.placements.Placement) placement_order:
            the optional order in which placements should be examined
        :return: DSG targets (map of placement tuple and filename)
        :rtype: tuple(DataSpecificationTargets, dict(tuple(int,int,int), int))
        :raises ConfigurationException:
            If the DSG asks to use more SDRAM than is available.
        """
        # pylint: disable=too-many-arguments, too-many-locals
        # pylint: disable=attribute-defined-outside-init
        self._machine = machine
        self._hostname = hostname
        self._report_dir = report_default_directory
        self._write_text = write_text_specs

        # iterate though vertices and call generate_data_spec for each
        # vertex
        targets = DataSpecificationTargets(machine, self._report_dir)

        if placement_order is None:
            placement_order = placements.placements

        progress = ProgressBar(
            placements.n_placements, "Generating data specifications")
        vertices_to_reset = list()
        for placement in progress.over(placement_order):
            # Try to generate the data spec for the placement
            vertex = placement.vertex
            generated = self.__generate_data_spec_for_vertices(
                placement, vertex, targets, data_n_timesteps)

            if generated and isinstance(
                    vertex, AbstractRewritesDataSpecification):
                vertices_to_reset.append(vertex)

            # If the spec wasn't generated directly, and there is an
            # application vertex, try with that
            if not generated and vertex.app_vertex is not None:
                generated = self.__generate_data_spec_for_vertices(
                    placement, vertex.app_vertex, targets, data_n_timesteps)
                if generated and isinstance(
                        vertex.app_vertex, AbstractRewritesDataSpecification):
                    vertices_to_reset.append(vertex.app_vertex)

        # Ensure that the vertices know their regions have been reloaded
        for vertex in vertices_to_reset:
            vertex.set_reload_required(False)

        return targets, self._region_sizes

    def __generate_data_spec_for_vertices(
            self, pl, vertex, targets, data_n_timesteps):
        """
        :param ~.Placement pl: placement of machine graph to cores
        :param ~.AbstractVertex vertex: the specific vertex to write DSG for.
        :param DataSpecificationTargets targets:
        :return: True if the vertex was data spec-able, False otherwise
        :rtype: bool
        :raises ConfigurationException: if things don't fit
        """
        # if the vertex can generate a DSG, call it
        if not isinstance(vertex, AbstractGeneratesDataSpecification):
            return False

        with targets.create_data_spec(pl.x, pl.y, pl.p) as data_writer:
            report_writer = get_report_writer(
                pl.x, pl.y, pl.p, self._hostname,
                self._report_dir, self._write_text)
            spec = DataSpecificationGenerator(data_writer, report_writer)

            # generate the DSG file
            vertex.generate_data_specification(spec, pl)

            # Check the memory usage
            self._region_sizes[pl.x, pl.y, pl.p] = (
                APP_PTR_TABLE_BYTE_SIZE + sum(spec.region_sizes))

            # extracts the int from the numpy data type generated
            if not isinstance(self._region_sizes[pl.x, pl.y, pl.p], int):
                self._region_sizes[pl.x, pl.y, pl.p] =\
                    self._region_sizes[pl.x, pl.y, pl.p].item()

            self._vertices_by_chip[pl.x, pl.y].append(pl.vertex)
            self._sdram_usage[pl.x, pl.y] += sum(spec.region_sizes)
            if (self._sdram_usage[pl.x, pl.y] <=
                    self._machine.get_chip_at(pl.x, pl.y).sdram.size):
                return True

        # creating the error message which contains the memory usage of
        #  what each core within the chip uses and its original
        # estimate.
        memory_usage = "\n".join((
            "    {}: {} (total={}, estimated={})".format(
                vert, self._region_sizes[pl.x, pl.y, pl.p],
                sum(self._region_sizes[pl.x, pl.y, pl.p]),
                vert.resources_required.sdram.get_total_sdram(
                    data_n_timesteps))
            for vert in self._vertices_by_chip[pl.x, pl.y]))

        raise ConfigurationException(
            "Too much SDRAM has been used on {}, {}.  Vertices and"
            " their usage on that chip is as follows:\n{}".format(
                pl.x, pl.y, memory_usage))
