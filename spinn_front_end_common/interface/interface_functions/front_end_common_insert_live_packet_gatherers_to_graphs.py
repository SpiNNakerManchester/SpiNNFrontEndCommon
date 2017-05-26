from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utility_models.live_packet_gather \
    import LivePacketGather
from spinn_front_end_common.utility_models.live_packet_gather_machine_vertex\
    import LivePacketGatherMachineVertex


class FrontEndCommonInsertLivePacketGatherersToGraphs(object):
    """ function to add LPG's as required into a given graph
    
    """

    def __call__(
            self, live_packet_gatherers, machine, application_graph=None,
            machine_graph=None):
        """ call that adds LPG vertices on ethernet connected chips as 
        required. 
        
        :param live_packet_gatherers: the LPG parameters requested by the \
        script
        :param machine: the spinnaker machine as discovered
        :param application_graph: the application graph
        :param machine_graph: the machine graph
        :return: mapping between LPG params and LPG vertex 
        """

        # deduce which graph to add the LPG's too.
        if application_graph is not None and machine_graph is not None:
            raise exceptions.ConfigurationException(
                "The insertion of LivePacketGatherers require 1 graph with "
                "at least one vertex in it. Not two. Please fix and try again")

        graph = None
        lpg_vertex = None
        lpg_params_to_vertex_mapping = dict()
        if application_graph is not None:
            graph = application_graph
            lpg_vertex = LivePacketGather
        elif machine_graph is not None:
            graph = machine_graph
            lpg_vertex = LivePacketGatherMachineVertex
        else:
            raise exceptions.ConfigurationException(
                "The insertion of LivePacketGatherers require a graph with "
                "at least one vertex in it. Please fix and try again")

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
            chip = self._get_ethernet_chip(
                machine, board_specific_lpg_params.board_address)
            self._create_and_add_vertex(
                graph, lpg_vertex, board_specific_lpg_params, chip,
                lpg_params_to_vertex_mapping)
            del working_live_packet_gatherers_parameters[
                board_specific_lpg_params]

        # for ever ethernet connected chip, add the rest of the LPG types
        for chip in machine.ethernet_connected_chips:
            for live_packet_gatherer_param in \
                    working_live_packet_gatherers_parameters:
                self._create_and_add_vertex(
                    graph, lpg_vertex, live_packet_gatherer_param, chip,
                    lpg_params_to_vertex_mapping)

        return lpg_params_to_vertex_mapping
                
    @staticmethod
    def _create_and_add_vertex(
            graph, lpg_vertex, params, chip, lpg_params_to_vertex_mapping):
        """ creates a given LPG vertex and adds it to the graph with a \ 
        placement constraint stating to place it on the chip provided.
        
        :param graph: the graph to place the vertex into
        :type graph: Application Graph or Machine graph
        :param lpg_vertex: the lpg type to create for the vertex
        :type lpg_vertex: LivePacketGather/LivePacketGatherMachineVertex
        :param params: the params of the vertex
        :type params: 
        :param chip: the chip to place it on
        :type chip: spinnMachine.chip.Chip
        :rtype: None 
        """
        live_packet_gatherer_vertex = lpg_vertex(
            label=params.label,
            ip_address=params.hostname,
            port=params.port,
            tag=params.tag,
            board_address=params.board_address,
            strip_sdp=params.strip_sdp,
            use_prefix=params.use_prefix,
            key_prefix=params.key_prefix,
            prefix_type=params.prefix_type,
            message_type=params.message_type,
            right_shift=params.right_shift,
            payload_as_time_stamps=params.payload_as_time_steps,
            use_payload_prefix= params.use_payload_prefix,
            payload_prefix=params.payload_prefix,
            payload_right_shift=params.payload_right_shift,
            number_of_packets_sent_per_time_step=
            params.number_of_packets_sent_per_time_step,
            constraints=[PlacerChipAndCoreConstraint(x=chip.x, y=chip.y)])
        graph.add_vertex(live_packet_gatherer_vertex)
        lpg_params_to_vertex_mapping[params] = live_packet_gatherer_vertex

    @staticmethod
    def _get_ethernet_chip(machine, board_address):
        """ locate the chip which supports a given board address (aka its 
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
