# Copyright (c) 2020 The University of Manchester
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
from pacman.model.graphs.application import ApplicationVertex
from spinn_front_end_common.interface.provenance import ProvenanceWriter
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD
from spinn_utilities.abstract_base import abstractmethod


class TDMAAwareApplicationVertex(ApplicationVertex):
    """
    An application vertex that contains the code for using TDMA to spread
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

    def __init__(self, label, max_atoms_per_core, splitter=None):
        """
        :param label: The name of the vertex.
        :type label: str or None
        :param int max_atoms_per_core: The max number of atoms that can be
            placed on a core, used in partitioning.
        :type splitter:
            ~pacman.model.partitioner_interfaces.AbstractSplitterCommon
            or None
        """
        super().__init__(label, max_atoms_per_core, splitter=splitter)
        self.__clocks_between_cores = None
        self.__n_slots = None
        self.__clocks_between_spikes = None
        self.__initial_offset = None
        self.__n_phases = None
        self.__clocks_per_cycle = None

    def set_initial_offset(self, new_value):
        """
        Sets the initial offset.

        :param int new_value: the new initial offset, in clock ticks
        """
        self.__initial_offset = new_value

    def get_n_phases(self):
        """
        Compute the number of phases needed for this application vertex.
        This is the maximum number of packets any machine vertex created
        by this application vertex can send in one simulation time step,
        which defaults to the number of atoms in the graph.

        :rtype: int
        """
        return self.n_atoms

    def generate_tdma_data_specification_data(self, vertex_index):
        """
        Generates the TDMA configuration data needed for the data spec.

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
        """
        The number of bytes needed by the TDMA data.

        :rtype: int
        """
        return self._TDMA_N_ELEMENTS * BYTES_PER_WORD

    def set_other_timings(
            self, clocks_between_cores, n_slots, clocks_between_spikes,
            n_phases, clocks_per_cycle):
        """
        Sets the other timings needed for the TDMA.

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

    @abstractmethod
    def get_n_cores(self):
        """
        Get the number of cores this application vertex is using in the TDMA.

        :return: the number of cores to use in the TDMA
        :rtype: int
        """

    def get_tdma_provenance_item(
            self,  x, y, p, desc_label, tdma_slots_missed):
        """
        Get the provenance item used for the TDMA provenance.

        :param int x: x coordinate of the chip where this core
        :param int y: y coordinate of the core where this core
        :param int p: virtual id of the core
        :param str desc_label: a descriptive label for the vertex
        :param int tdma_slots_missed: the number of TDMA slots missed
        """
        with ProvenanceWriter() as db:
            db.insert_core(
                x, y, p, self._TDMA_MISSED_SLOTS_NAME, tdma_slots_missed)
            if tdma_slots_missed > 0:
                db.insert_report(
                    f"The {desc_label} had the TDMA fall behind by "
                    f"{tdma_slots_missed} times.  Try increasing the "
                    "time_between_cores in the corresponding .cfg")
