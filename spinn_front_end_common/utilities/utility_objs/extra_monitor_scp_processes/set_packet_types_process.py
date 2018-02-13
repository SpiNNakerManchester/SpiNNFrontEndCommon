from spinn_front_end_common.utilities.utility_objs.extra_monitor_scp_messages.\
    set_reinjection_packet_types_message import \
    SetReinjectionPacketTypesMessage
from spinnman.processes.abstract_multi_connection_process \
    import AbstractMultiConnectionProcess


class SetPacketTypesProcess(AbstractMultiConnectionProcess):
    def __init__(self, connection_selector):
        AbstractMultiConnectionProcess.__init__(self, connection_selector)

    def set_packet_types(self, core_subsets, point_to_point, multicast,
                         nearest_neighbour, fixed_route, command_code):
        """
        :param core_subsets: sets of cores to send command to
        :param point_to_point: bool stating if point to point should be set
        :param multicast: bool stating if multicast should be set
        :param nearest_neighbour: bool stating if nearest neighbour should be \
        set
        :param fixed_route: bool stating if fixed route should be set
        :param command_code: the command code used by extra monitor cores 
        for setting packet types
        :rtype: None
        """

        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(SetReinjectionPacketTypesMessage(
                    core_subset.x, core_subset.y, processor_id, multicast,
                    point_to_point, fixed_route, nearest_neighbour,
                    command_code))
        self._finish()
        self.check_for_error()
