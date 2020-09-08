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
from spinn_front_end_common.interface.provenance.\
    provides_provenance_data_from_machine_impl import add_name
from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem
from spinn_front_end_common.utilities import constants

# The number of clock cycles per nanosecond
_CLOCKS_PER_NS = 200


class TDMAAwareApplicationVertex(ApplicationVertex):
    """
    vertex that contains the code for handling the containing of TDMA code.
    """

    # 1. initial expected time, 2. min expected time, 3. time between cores
    TDMA_N_ELEMENTS = 4

    TDMA_MISSED_SLOTS_NAME = "Number_of_times_the_tdma_fell_behind"
    TDMA_MISSED_SLOTS_MESSAGE = (
        "The TDMA fell behind by {} times on core {}, {}, {}. "
        "try increasing the time_between_cores in the corresponding .cfg")

    def __init__(self, label, constraints, max_atoms_per_core):
        ApplicationVertex.__init__(
            self, label, constraints, max_atoms_per_core)
        self.__time_between_cores = None
        self.__n_slots = None
        self.__time_between_spikes = None
        self.__initial_offset = None
        self.__n_phases = None
        self.__ns_per_cycle = None

    def set_initial_offset(self, new_value):
        self.__initial_offset = new_value

    def find_n_phases_for(self, app_vertex, machine_graph, n_keys_map):
        max_keys_seen_so_far = 0
        for machine_vertex in app_vertex.machine_vertices:
            max_keys_needed = 0
            outgoing_partitions = (
                machine_graph.get_outgoing_edge_partitions_starting_at_vertex(
                    machine_vertex))
            for outgoing_partition in outgoing_partitions:
                keys_this_partition = n_keys_map.n_keys_for_partition(
                    outgoing_partition)
                max_keys_needed += keys_this_partition
            if max_keys_seen_so_far < max_keys_needed:
                max_keys_seen_so_far = max_keys_needed
        return max_keys_seen_so_far

    def generate_tdma_data_specification_data(self, vertex_index):
        core_slot = vertex_index & self.__n_slots
        offset_clocks = (self.__initial_offset +
                         (self.__time_between_cores * core_slot) *
                         _CLOCKS_PER_NS)
        tdma_clocks = (self.__n_phases * self.__time_between_spikes *
                       _CLOCKS_PER_NS)
        total_clocks = _CLOCKS_PER_NS * self.__ns_per_cycle
        initial_expected_time = total_clocks - offset_clocks
        min_expected_time = initial_expected_time - tdma_clocks
        clocks_between_sends = self.__time_between_spikes * _CLOCKS_PER_NS
        return [initial_expected_time, min_expected_time,
                clocks_between_sends]

    @property
    def tdma_sdram_size_in_bytes(self):
        return self.TDMA_N_ELEMENTS * constants.BYTES_PER_WORD

    def set_other_timings(
        self, time_between_cores, n_slots, time_between_spikes, n_phases,
        ns_per_cycle):
        self.__time_between_cores = time_between_cores
        self.__n_slots = n_slots
        self.__time_between_spikes = time_between_spikes
        self.__n_phases = n_phases
        self.__ns_per_cycle = ns_per_cycle

    def get_n_cores(self, app_vertex):
        return len(app_vertex.vertex_slices)

    def get_tdma_provenance_item(self, names, x, y, p, tdma_slots_missed):
        return ProvenanceDataItem(
            add_name(names, self.TDMA_MISSED_SLOTS_NAME),
            tdma_slots_missed, report=tdma_slots_missed > 0,
            message=self.TDMA_MISSED_SLOTS_MESSAGE.format(
                tdma_slots_missed, x, y, p))
