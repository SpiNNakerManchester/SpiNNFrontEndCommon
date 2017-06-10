# spinn front end common imports
from spinn_front_end_common.utility_models.live_packet_gather \
    import LivePacketGather
from spinn_front_end_common.utility_models.live_packet_gather_machine_vertex\
    import LivePacketGatherMachineVertex

# pacman imports
from pacman.model.graphs.common.slice import Slice
from pacman.model.constraints.placer_constraints\
    .placer_chip_and_core_constraint import PlacerChipAndCoreConstraint

from spinn_utilities.progress_bar import ProgressBar

from collections import defaultdict


class FrontEndCommonInsertLivePacketGatherersToGraphs(object):
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
        progress_bar = ProgressBar(
            len(machine.ethernet_connected_chips),
            string_describing_what_being_progressed=(
                "Adding Live Packet Gatherers to Graph"))

        # Keep track of the vertices added by parameters and board address
        lpg_params_to_vertex_mapping = defaultdict(dict)

        # for every Ethernet connected chip, add the gatherers required
        for chip in machine.ethernet_connected_chips:
            for live_packet_gatherer_params in live_packet_gatherer_parameters:
                if (live_packet_gatherer_params.board_address is None or
                    live_packet_gatherer_params.board_address ==
                        chip.ip_address):
                    machine_vertex = None
                    if application_graph is not None:
                        vertex_slice = Slice(0, 0)
                        application_vertex = self._create_vertex(
                            LivePacketGather, live_packet_gatherer_params)
                        application_graph.add_vertex(application_vertex)
                        resources_required = \
                            application_vertex.get_resources_used_by_atoms(
                                vertex_slice)
                        machine_vertex = \
                            application_vertex.create_machine_vertex(
                                vertex_slice, resources_required)
                        graph_mapper.add_vertex_mapping(
                            machine_vertex, vertex_slice, application_vertex)
                    else:
                        machine_vertex = self._create_vertex(
                            LivePacketGatherMachineVertex,
                            live_packet_gatherer_params)

                    machine_vertex.add_constraint(PlacerChipAndCoreConstraint(
                        x=chip.x, y=chip.y))
                    machine_graph.add_vertex(machine_vertex)
                    lpg_params_to_vertex_mapping[live_packet_gatherer_params][
                        chip.x, chip.y] = machine_vertex

            # update progress bar
            progress_bar.update()

        # update progress bar
        progress_bar.end()

        return lpg_params_to_vertex_mapping

    @staticmethod
    def _create_vertex(lpg_vertex_class, params):
        """ Creates a Live Packet Gather Vertex

        :param lpg_vertex_class: the type to create for the vertex
        :param params: the params of the vertex
        :return the vertex built
        """
        return lpg_vertex_class(
            label=params.label,
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
                params.number_of_packets_sent_per_time_step))
