# Copyright (c) 2020-2021 The University of Manchester
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
from pacman.model.graphs.application import ApplicationVertex
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD
from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem
from spinn_front_end_common.interface.provenance.\
    provides_provenance_data_from_machine_impl import (
        add_name)


class TDMAAwareApplicationVertex(ApplicationVertex):
    """ An application vertex that contains the code for using TDMA to spread\
        packet transmission to try to avoid overloading any SpiNNaker routers.
    """

    __slots__ = (
        "__initial_offset",
        "__n_phases",
        "__n_slots",
        "__clocks_per_cycle",
        "__clocks_between_cores",
        "__clocks_between_spikes")

    # 1. initial expected time, 2. min expected time, 3. time between cores
    _TDMA_N_ELEMENTS = 3

    _TDMA_MISSED_SLOTS_NAME = "Number_of_times_the_tdma_fell_behind"
    _TDMA_MISSED_SLOTS_MESSAGE = (
        "The TDMA fell behind by {} times on core {}, {}, {}. "
        "try increasing the time_between_cores in the corresponding .cfg")

    def __init__(self, label, constraints, max_atoms_per_core, splitter=None):
        """
        :param label: The name of the vertex.
        :type label: str or None
        :param constraints: The initial constraints of the vertex.
        :type constraints:
            iterable(~pacman.model.constraints.AbstractConstraint) or None
        :param int max_atoms_per_core: The max number of atoms that can be
            placed on a core, used in partitioning.
        :type splitter:
            ~pacman.model.partitioner_interfaces.AbstractSplitterCommon
            or None
        :raise PacmanInvalidParameterException:
            If one of the constraints is not valid
        """
        super().__init__(
            label, constraints, max_atoms_per_core, splitter=splitter)
        self.__clocks_between_cores = None
        self.__n_slots = None
        self.__clocks_between_spikes = None
        self.__initial_offset = None
        self.__n_phases = None
        self.__clocks_per_cycle = None

    def set_initial_offset(self, new_value):
        """ Sets the initial offset

        :param int new_value: the new initial offset, in clock ticks
        """
        self.__initial_offset = new_value

    def find_n_phases_for(self, machine_graph, n_keys_map):
        """ Compute the number of phases needed for this application vertex. \
            This is the maximum number of packets any machine vertex created \
            by this application vertex can send in one simulation time step.

        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
        :param n_keys_map:
        :type n_keys_map:
            ~pacman.model.routing_info.AbstractMachinePartitionNKeysMap
        :rtype: int
        """
        return max(
            sum(
                n_keys_map.n_keys_for_partition(outgoing_partition)
                for outgoing_partition in
                machine_graph.get_multicast_edge_partitions_starting_at_vertex(
                    machine_vertex))
            for machine_vertex in self.machine_vertices)

    def generate_tdma_data_specification_data(self, vertex_index):
        """ Generates the TDMA configuration data needed for the data spec

        :param int vertex_index: the machine vertex index in the pop
        :return: array of data to write.
        :rtype: list(int)
        """
        core_slot = vertex_index & self.__n_slots
        offset_clocks = (
            self.__initial_offset + (self.__clocks_between_cores * core_slot))
        tdma_clocks = self.__n_phases * self.__clocks_between_spikes
        initial_expected_time = self.__clocks_per_cycle - offset_clocks
        min_expected_time = initial_expected_time - tdma_clocks
        return [initial_expected_time, min_expected_time,
                self.__clocks_between_spikes]

    @property
    def tdma_sdram_size_in_bytes(self):
        """ The number of bytes needed by the TDMA data

        :rtype: int
        """
        return self._TDMA_N_ELEMENTS * BYTES_PER_WORD

    def set_other_timings(
            self, clocks_between_cores, n_slots, clocks_between_spikes,
            n_phases, clocks_per_cycle):
        """ Sets the other timings needed for the TDMA.

        :param int clocks_between_cores: clock cycles between cores
        :param int n_slots: the number of slots
        :param int clocks_between_spikes:
            the clock cycles to wait between spikes
        :param int n_phases: the number of phases
        :param int clocks_per_cycle: the number of clock cycles per TDMA cycle
        """
        self.__clocks_between_cores = clocks_between_cores
        self.__n_slots = n_slots
        self.__clocks_between_spikes = clocks_between_spikes
        self.__n_phases = n_phases
        self.__clocks_per_cycle = clocks_per_cycle

    def get_n_cores(self):
        """ Get the number of cores this application vertex is using in \
            the TDMA.

        :return: the number of cores to use in the TDMA
        :rtype: int
        """
        return len(self.vertex_slices)

    def get_tdma_provenance_item(self, names, x, y, p, tdma_slots_missed):
        """ Get the provenance item used for the TDMA provenance

        :param list(str) names: the names for the provenance data item
        :param int x: chip x
        :param int y: chip y
        :param int p: processor id
        :param int tdma_slots_missed: the number of TDMA slots missed
        :return: the provenance data item
        :rtype: ProvenanceDataItem
        """
        return ProvenanceDataItem(
            add_name(names, self._TDMA_MISSED_SLOTS_NAME),
            tdma_slots_missed, report=(tdma_slots_missed > 0),
            message=self._TDMA_MISSED_SLOTS_MESSAGE.format(
                tdma_slots_missed, x, y, p))
