from spinn_utilities.progress_bar import ProgressBar

from spinn_front_end_common.interface.buffer_management import BufferManager
from spinn_front_end_common.interface.buffer_management.buffer_models \
    import AbstractSendsBuffersFromHost, AbstractReceiveBuffersToHost


class BufferManagerCreator(object):
    __slots__ = []

    def __call__(
            self, placements, tags, txrx, store_data_in_file,
            uses_advanced_monitors, extra_monitor_cores=None,
            extra_monitor_to_chip_mapping=None,
            extra_monitor_cores_to_ethernet_connection_map=None, machine=None):
        progress = ProgressBar(placements.placements, "Initialising buffers")

        # Create the buffer manager
        buffer_manager = BufferManager(
            placements=placements, tags=tags, transceiver=txrx,
            store_to_file=store_data_in_file,
            extra_monitor_cores=extra_monitor_cores,
            extra_monitor_cores_to_ethernet_connection_map=
            extra_monitor_cores_to_ethernet_connection_map,
            extra_monitor_to_chip_mapping=extra_monitor_to_chip_mapping,
            machine=machine, uses_advanced_monitors=uses_advanced_monitors)

        for placement in progress.over(placements.placements):
            if isinstance(placement.vertex, AbstractSendsBuffersFromHost):
                if placement.vertex.buffering_input():
                    buffer_manager.add_sender_vertex(placement.vertex)

            if isinstance(placement.vertex, AbstractReceiveBuffersToHost):
                buffer_manager.add_receiving_vertex(placement.vertex)

        return buffer_manager
