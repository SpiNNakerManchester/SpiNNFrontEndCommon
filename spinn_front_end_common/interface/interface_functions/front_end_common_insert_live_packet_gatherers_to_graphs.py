# spinn front end common imports
from pacman.model.graphs.common.slice import Slice
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utility_models.live_packet_gather \
    import LivePacketGather
from spinn_front_end_common.utility_models.live_packet_gather_machine_vertex\
    import LivePacketGatherMachineVertex

# pacman imports
from pacman.model.constraints.placer_constraints\
    .placer_chip_and_core_constraint import PlacerChipAndCoreConstraint
from spinn_utilities.progress_bar import ProgressBar


class FrontEndCommonInsertLivePacketGatherersToGraphs(object):
    """ function to add LPG's as required into a given graph
    """

    def __call__(
            self, live_packet_gatherers, machine, machine_graph,
            application_graph=None, graph_mapper=None):
        """ call that adds LPG vertices on ethernet connected chips as\
         required.

        :param live_packet_gatherers: the LPG parameters requested by the \
        script
        :param machine: the spinnaker machine as discovered
        :param application_graph: the application graph
        :param machine_graph: the machine graph
        :return: mapping between LPG params and LPG vertex
        """
        lpg_params_to_vertex_mapping = dict()

        # create progress bar
        progress_bar = ProgressBar(
            total_number_of_things_to_do=(
                len(live_packet_gatherers) *
                len(machine.ethernet_connected_chips)),
            string_describing_what_being_progressed=(
                "Inserting LPG vertices into the graphs"))

        # clone the live_packet_gatherer parameters holder for usage
        working_live_packet_gatherers_parameters = dict(live_packet_gatherers)

        # locate LPG's which have specific board addresses to their ethernet
        # connected chips.
        board_specific_lpgs = list()
        for live_packet_gatherer_params in \
                working_live_packet_gatherers_parameters:
            if live_packet_gatherer_params.board_address is not None:
                board_specific_lpgs.append(live_packet_gatherer_params)

        # add LPG's which have specific board addresses
        for board_specific_lpg_params in board_specific_lpgs:
            # find chip
            chip = self._get_ethernet_chip(
                machine, board_specific_lpg_params.board_address)

            # create and add vetex to graph
            machine_live_packet_gatherer_vertex = self._create_and_add_vertex(
                machine_graph, LivePacketGatherMachineVertex,
                board_specific_lpg_params, chip)

            # update mapping
            lpg_params_to_vertex_mapping[board_specific_lpg_params] = list()
            lpg_params_to_vertex_mapping[board_specific_lpg_params].append(
                machine_live_packet_gatherer_vertex)

            # remove from working copy
            del working_live_packet_gatherers_parameters[
                board_specific_lpg_params]

            # update app graph and graph mapper if required
            self._update_app_graph_if_needed(
                application_graph, graph_mapper,
                machine_live_packet_gatherer_vertex,
                board_specific_lpg_params, chip)

            # update progress bar
            progress_bar.update()

        # for ever ethernet connected chip, add the rest of the LPG types
        for chip in machine.ethernet_connected_chips:
            for live_packet_gatherer_param in \
                    working_live_packet_gatherers_parameters:
                machine_live_packet_gatherer_vertex = \
                    self._create_and_add_vertex(
                        machine_graph, LivePacketGatherMachineVertex,
                        live_packet_gatherer_param, chip)

                # create list for this lpg param set
                if live_packet_gatherer_param not in \
                        lpg_params_to_vertex_mapping:
                    lpg_params_to_vertex_mapping[
                        live_packet_gatherer_param] = list()

                # add to the list for this param set
                lpg_params_to_vertex_mapping[
                    live_packet_gatherer_param].append(
                        machine_live_packet_gatherer_vertex)

                # update app graph and graph mapper if required
                self._update_app_graph_if_needed(
                    application_graph, graph_mapper,
                    machine_live_packet_gatherer_vertex,
                    live_packet_gatherer_param, chip)

                # update progress bar
                progress_bar.update()

        # update progress bar
        progress_bar.end()

        return lpg_params_to_vertex_mapping

    def _update_app_graph_if_needed(
            self, application_graph, graph_mapper,
            machine_live_packet_gatherer_vertex,
            board_specific_lpg_params, chip):
        """ adds to the application graph and graph mapper if needed

        :param application_graph: the app graph to add to
        :param graph_mapper: the graph mapper object
        :param machine_live_packet_gatherer_vertex: the machine vertex LPG
        :param board_specific_lpg_params: the LPG params
        :param chip:  the chip it resides on
        :rtype: None
        """
        if application_graph is not None:
            app_live_packet_gatherer_vertex = self._create_and_add_vertex(
                application_graph, LivePacketGather,
                board_specific_lpg_params, chip)
            graph_mapper.add_vertex_mapping(
                machine_live_packet_gatherer_vertex, Slice(0, 0),
                app_live_packet_gatherer_vertex)

    @staticmethod
    def _create_and_add_vertex(graph, lpg_vertex, params, chip):
        """ creates a given LPG vertex and adds it to the graph with a \
        placement constraint stating to place it on the chip provided.

        :param graph: the graph to place the vertex into
        :type graph: Application Graph or Machine graph
        :param lpg_vertex: the lpg type to create for the vertex
        :type lpg_vertex: LivePacketGather/LivePacketGatherMachineVertex
        :param params: the params of the vertex
        :type params: LPG params object
        :param chip: the chip to place it on
        :type chip: spinnMachine.chip.Chip
        :return the vertex built
        :rtype:  LivePacketGather/LivePacketGatherMachineVertex
        """
        live_packet_gatherer_vertex = lpg_vertex(
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
                params.number_of_packets_sent_per_time_step),
            constraints=[PlacerChipAndCoreConstraint(x=chip.x, y=chip.y)])
        graph.add_vertex(live_packet_gatherer_vertex)
        return live_packet_gatherer_vertex

    @staticmethod
    def _get_ethernet_chip(machine, board_address):
        """ locate the chip which supports a given board address (aka its\
         ip_address)

        :param machine: the spinnaker machine
        :param board_address:  the board address to locate the chip of.
        :return: The chip that supports that board address
        :raises ConfigurationException: when that board address has no chip\
        associated with it
        """
        for chip in machine.ethernet_connected_chips:
            if chip.ip_address == board_address:
                return chip
        raise exceptions.ConfigurationException(
            "cannot find the ethernet connected chip which supports the "
            "board address {}".format(board_address))
