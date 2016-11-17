from spinn_machine.utilities.progress_bar import ProgressBar

from spinn_front_end_common.interface.buffer_management.buffer_manager import \
    BufferManager
from spinn_front_end_common.interface.buffer_management.buffer_models\
    .abstract_sends_buffers_from_host import AbstractSendsBuffersFromHost
from spinn_front_end_common.interface.buffer_management.buffer_models\
    .abstract_receive_buffers_to_host \
    import AbstractReceiveBuffersToHost


class FrontEndCommonBufferManagerCreator(object):

    __slots__ = []

    def __call__(
            self, placements, tags, txrx, write_reload_files, app_data_folder):

        progress_bar = ProgressBar(
            len(list(placements.placements)), "Initialising buffers")

        # Create the buffer manager
        buffer_manager = BufferManager(
            placements, tags, txrx, write_reload_files, app_data_folder)

        for placement in placements.placements:
            if isinstance(placement.vertex, AbstractSendsBuffersFromHost):
                if placement.vertex.buffering_input():
                    buffer_manager.add_sender_vertex(placement.vertex)

            if isinstance(placement.vertex, AbstractReceiveBuffersToHost):
                buffer_manager.add_receiving_vertex(placement.vertex)

            progress_bar.update()
        progress_bar.end()

        return buffer_manager
