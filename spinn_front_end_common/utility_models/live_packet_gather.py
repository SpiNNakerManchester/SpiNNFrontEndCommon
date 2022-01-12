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

from pacman.model.graphs.application import ApplicationVertex
from .live_packet_gather_machine_vertex import LivePacketGatherMachineVertex


class LivePacketGather(ApplicationVertex):
    """ A model which stores all the events it receives during a timer tick\
        and then compresses them into Ethernet packets and sends them out of\
        a SpiNNaker machine.
    """

    __slots__ = ["__lpg_params"]

    def __init__(self, lpg_params, constraints=None):
        """
        :param LivePacketGatherParameters lpg_params:
        :param constraints:
        :type constraints:
            iterable(~pacman.model.constraints.AbstractConstraint)
        """
        label = lpg_params.label or "Live Packet Gatherer"
        super(LivePacketGather, self).__init__(label, constraints)
        self.__lpg_params = lpg_params
        self._incoming_edges = list()

    def add_incoming_edge(self, edge):
        self._incoming_edges.append(edge)

    @property
    def n_atoms(self):
        return 1

    def __get_key_translation_sdram(self):
        if not self._lpg_params.translate_keys:
            return 0
        n_entries = 0
        for edge in self._incoming_edges:
            n_entries += len(
                edge.pre_vertex.splitter.get_in_coming_slices()[0])
        return n_entries * LivePacketGatherMachineVertex._KEY_ENTRY_SIZE

    @property
    def parameters(self):
        """ Get the parameters of this vertex

        :rtype: LivePacketGatherPatameters
        """
        return self.__lpg_params
