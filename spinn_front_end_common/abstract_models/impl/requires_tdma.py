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

from spinn_front_end_common.abstract_models.abstract_requires_tdma import \
    AbstractRequiresTDMA
from spinn_front_end_common.interface.provenance.\
    provides_provenance_data_from_machine_impl import add_name
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem
from spinn_utilities.overrides import overrides


class RequiresTDMA(AbstractRequiresTDMA):

    # 1. initial expected time, 2. min expected time, 3. time between cores
    TDMA_N_ELEMENTS = 4

    TDMA_MISSED_SLOTS_NAME = "Number_of_times_the_tdma_fell_behind"
    TDMA_MISSED_SLOTS_MESSAGE = (
        "The TDMA fell behind by {} times on core {}, {}, {}. "
        "try increasing the time_between_cores in the corresponding .cfg")

    def __init__(self):
        AbstractRequiresTDMA.__init__(self)
        self.__time_between_cores = None
        self.__n_slots = None
        self.__time_between_spikes = None
        self.__initial_offset = None

    @overrides(AbstractRequiresTDMA.set_initial_offset)
    def set_initial_offset(self, new_value):
        self.__initial_offset = new_value

    @overrides(AbstractRequiresTDMA.find_n_phases_for)
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

    @overrides(AbstractRequiresTDMA.generate_tdma_data_specification_data)
    def generate_tdma_data_specification_data(self, vertex_index):
        return [
            vertex_index & self.__n_slots, self.__time_between_spikes,
            self.__time_between_cores, self.__initial_offset]

    @property
    @overrides(AbstractRequiresTDMA.tdma_sdram_size_in_bytes)
    def tdma_sdram_size_in_bytes(self):
        return self.TDMA_N_ELEMENTS * constants.BYTES_PER_WORD

    @overrides(AbstractRequiresTDMA.set_other_timings)
    def set_other_timings(
            self, time_between_cores, n_slots, time_between_spikes):
        self.__time_between_cores = time_between_cores
        self.__n_slots = n_slots
        self.__time_between_spikes = time_between_spikes

    @overrides(AbstractRequiresTDMA.get_n_cores)
    def get_n_cores(self, app_vertex):
        return len(app_vertex.vertex_slices)

    @overrides(AbstractRequiresTDMA.get_tdma_provenance_item)
    def get_tdma_provenance_item(self, names, x, y, p, tdma_slots_missed):
        return ProvenanceDataItem(
            add_name(names, self.TDMA_MISSED_SLOTS_NAME),
            tdma_slots_missed, report=tdma_slots_missed > 0,
            message=self.TDMA_MISSED_SLOTS_MESSAGE.format(
                tdma_slots_missed, x, y, p))
