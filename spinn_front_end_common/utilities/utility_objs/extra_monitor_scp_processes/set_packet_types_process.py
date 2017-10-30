from spinn_front_end_common.utilities.utility_objs.extra_monitor_scp_messages.\
    set_reinjection_packet_types_message import \
    SetReinjectionPacketTypesMessage
from spinnman.processes.abstract_multi_connection_process \
    import AbstractMultiConnectionProcess


class SetPacketTypesProcess(AbstractMultiConnectionProcess):
    def __init__(self, connection_selector):
        AbstractMultiConnectionProcess.__init__(self, connection_selector)

    def set_packet_types(self, packet_types, core_subsets):
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(SetReinjectionPacketTypesMessage(
                    core_subset.x, core_subset.y, processor_id, packet_types))
        self._finish()
        self.check_for_error()
