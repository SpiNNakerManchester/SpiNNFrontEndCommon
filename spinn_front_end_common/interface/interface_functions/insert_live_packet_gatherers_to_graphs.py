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

try:
    from collections.abc import defaultdict
except ImportError:
    from collections import defaultdict
from spinn_utilities.progress_bar import ProgressBar
from pacman.model.graphs.common import Slice
from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from spinn_front_end_common.utility_models import (
    LivePacketGather, LivePacketGatherMachineVertex)

_LPG_SLICE = Slice(0, 0)


class InsertLivePacketGatherersToGraphs(object):
    """ Adds LPGs as required into a given graph
    """

    def __call__(
            self, live_packet_gatherer_parameters, machine, machine_graph,
            application_graph=None):
        """ Add LPG vertices on Ethernet connected chips as required.

        :param live_packet_gatherer_parameters:\
            the Live Packet Gatherer parameters requested by the script
        :param machine: the SpiNNaker machine as discovered
        :param application_graph: the application graph
        :param machine_graph: the machine graph
        :return: mapping between LPG parameters and LPG vertex
        """
        # pylint: disable=too-many-arguments

        # create progress bar
        progress = ProgressBar(
            machine.ethernet_connected_chips,
            string_describing_what_being_progressed=(
                "Adding Live Packet Gatherers to Graph"))

        # Keep track of the vertices added by parameters and board address
        lpg_params_to_vertices = defaultdict(dict)

        # for every Ethernet connected chip, add the gatherers required
        if application_graph is not None:
            for chip in progress.over(machine.ethernet_connected_chips):
                for params in live_packet_gatherer_parameters:
                    if (params.board_address is None or
                            params.board_address == chip.ip_address):
                        lpg_params_to_vertices[params][chip.x, chip.y] = \
                            self._add_app_lpg_vertex(
                                application_graph, machine_graph, chip, params)
        else:
            for chip in progress.over(machine.ethernet_connected_chips):
                for params in live_packet_gatherer_parameters:
                    if (params.board_address is None or
                            params.board_address == chip.ip_address):
                        lpg_params_to_vertices[params][chip.x, chip.y] = \
                            self._add_mach_lpg_vertex(
                                machine_graph, chip, params)

        return lpg_params_to_vertices

    def _add_app_lpg_vertex(self, app_graph, m_graph, chip, params):
        """ Adds a LPG vertex to a machine graph that has an associated\
            application graph.
        """
        # pylint: disable=too-many-arguments
        app_vtx = self._create_vertex(LivePacketGather, params)
        app_graph.add_vertex(app_vtx)
        resources = app_vtx.get_resources_used_by_atoms(_LPG_SLICE)
        vtx = app_vtx.create_machine_vertex(
            _LPG_SLICE, resources, label="LivePacketGatherer")
        app_vtx.remember_associated_machine_vertex(vtx)
        vtx.add_constraint(ChipAndCoreConstraint(x=chip.x, y=chip.y))
        m_graph.add_vertex(vtx)
        return vtx

    def _add_mach_lpg_vertex(self, graph, chip, params):
        """ Adds a LPG vertex to a machine graph without an associated\
            application graph.
        """
        vtx = self._create_vertex(
            LivePacketGatherMachineVertex, params,
            app_vertex=None, vertex_slice=_LPG_SLICE)
        vtx.add_constraint(ChipAndCoreConstraint(x=chip.x, y=chip.y))
        graph.add_vertex(vtx)
        return vtx

    @staticmethod
    def _create_vertex(lpg_vertex_class, params, **kwargs):
        """ Creates a Live Packet Gather Vertex

        :param lpg_vertex_class: the type to create for the vertex
        :param params: the parameters of the vertex
        :return the vertex built
        """
        return lpg_vertex_class(
            hostname=params.hostname,
            port=params.port,
            tag=params.tag,
            board_address=params.board_address,
            strip_sdp=params.strip_sdp,
            use_prefix=params.use_prefix,
            key_prefix=params.key_prefix,
            prefix_type=params.prefix_type,
            message_type=params.message_type,
            right_shift=params.right_shift,
            payload_as_time_stamps=params.payload_as_time_stamps,
            use_payload_prefix=params.use_payload_prefix,
            payload_prefix=params.payload_prefix,
            payload_right_shift=params.payload_right_shift,
            number_of_packets_sent_per_time_step=(
                params.number_of_packets_sent_per_time_step),
            label="LiveSpikeReceiver", **kwargs)
