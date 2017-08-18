# spinn front end common imports
from spinn_front_end_common.utility_models.live_packet_gather \
    import LivePacketGather
from spinn_front_end_common.utility_models.live_packet_gather_machine_vertex \
    import LivePacketGatherMachineVertex

# pacman imports
from pacman.model.graphs.common import Slice
from pacman.model.constraints.placer_constraints\
    import ChipAndCoreConstraint

from spinn_utilities.progress_bar import ProgressBar

from collections import defaultdict


class InsertLivePacketGatherersToGraphs(object):
    """ function to add LPG's as required into a given graph
    """

    def __call__(
            self, live_packet_gatherer_parameters, machine, machine_graph,
            application_graph=None, graph_mapper=None):
        """ call that adds LPG vertices on Ethernet connected chips as\
            required.

        :param live_packet_gatherer_parameters:\
            the Live Packet Gatherer parameters requested by the script
        :param machine: the spinnaker machine as discovered
        :param application_graph: the application graph
        :param machine_graph: the machine graph
        :return: mapping between LPG params and LPG vertex
        """

        # create progress bar
        progress = ProgressBar(
            machine.ethernet_connected_chips,
            string_describing_what_being_progressed=(
                "Adding Live Packet Gatherers to Graph"))

        # Keep track of the vertices added by parameters and board address
        lpg_params_to_vertices = defaultdict(dict)

        # for every Ethernet connected chip, add the gatherers required
        for chip in progress.over(machine.ethernet_connected_chips):
            for lpg_params in live_packet_gatherer_parameters:
                if (lpg_params.board_address is None or
                        lpg_params.board_address == chip.ip_address):
                    lpg_params_to_vertices[lpg_params][chip.x, chip.y] = \
                        self._add_lpg_vertex(application_graph, graph_mapper,
                                             machine_graph, chip, lpg_params)

        return lpg_params_to_vertices

    def _add_lpg_vertex(self, app_graph, mapper, m_graph, chip, lpg_params):
        if app_graph is not None:
            vtx_slice = Slice(0, 0)
            app_vtx = self._create_vertex(LivePacketGather, lpg_params)
            app_graph.add_vertex(app_vtx)
            resources_required = app_vtx.get_resources_used_by_atoms(
                vtx_slice)
            m_vtx = app_vtx.create_machine_vertex(
                vtx_slice, resources_required)
            mapper.add_vertex_mapping(m_vtx, vtx_slice, app_vtx)
        else:
            m_vtx = self._create_vertex(
                LivePacketGatherMachineVertex, lpg_params)

        m_vtx.add_constraint(ChipAndCoreConstraint(x=chip.x, y=chip.y))
        m_graph.add_vertex(m_vtx)
        return m_vtx

    @staticmethod
    def _create_vertex(lpg_vertex_class, params):
        """ Creates a Live Packet Gather Vertex

        :param lpg_vertex_class: the type to create for the vertex
        :param params: the params of the vertex
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
            label="LiveSpikeReceiver")
