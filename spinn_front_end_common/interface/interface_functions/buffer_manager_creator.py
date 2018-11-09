from spinn_utilities.progress_bar import ProgressBar

from spinn_front_end_common.interface.buffer_management import BufferManager
from spinn_front_end_common.interface.buffer_management.buffer_models \
    import AbstractSendsBuffersFromHost, AbstractReceiveBuffersToHost


class BufferManagerCreator(object):
    __slots__ = []

    def __call__(
            self, placements, tags, txrx,
            uses_advanced_monitors, database_file, extra_monitor_cores=None,
            extra_monitor_to_chip_mapping=None,
            extra_monitor_cores_to_ethernet_connection_map=None, machine=None,
            fixed_routes=None, java_caller=None):
        """

        :param placements:
        :param tags:
        :param txrx:
        :param uses_advanced_monitors:
        :param extra_monitor_cores:
        :param extra_monitor_to_chip_mapping:
        :param extra_monitor_cores_to_ethernet_connection_map:
        :param machine:
        :param fixed_routes:
        :param database_file: The name of a file that contains (or will\
            contain) an SQLite database holding the data.
        :type database_file: str
        :return:
        """
        # pylint: disable=too-many-arguments
        progress = ProgressBar(placements.placements, "Initialising buffers")

        # Create the buffer manager
        buffer_manager = BufferManager(
            placements=placements, tags=tags, transceiver=txrx,
            extra_monitor_cores=extra_monitor_cores,
            extra_monitor_cores_to_ethernet_connection_map=(
                extra_monitor_cores_to_ethernet_connection_map),
            extra_monitor_to_chip_mapping=extra_monitor_to_chip_mapping,
            machine=machine, uses_advanced_monitors=uses_advanced_monitors,
            fixed_routes=fixed_routes, database_file=database_file,
            java_caller=java_caller)

        for placement in progress.over(placements.placements):
            if isinstance(placement.vertex, AbstractSendsBuffersFromHost):
                if placement.vertex.buffering_input():
                    buffer_manager.add_sender_vertex(placement.vertex)

            if isinstance(placement.vertex, AbstractReceiveBuffersToHost):
                buffer_manager.add_receiving_vertex(placement.vertex)

        return buffer_manager
