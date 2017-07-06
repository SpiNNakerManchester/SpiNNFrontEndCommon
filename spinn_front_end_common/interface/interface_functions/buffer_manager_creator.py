from spinn_utilities.progress_bar import ProgressBar

from spinn_front_end_common.interface.buffer_management import BufferManager
from spinn_front_end_common.interface.buffer_management.buffer_models \
    import AbstractSendsBuffersFromHost, AbstractReceiveBuffersToHost


class BufferManagerCreator(object):
    __slots__ = []

    def __call__(
            self, placements, tags, txrx):
        progress = ProgressBar(placements.placements, "Initialising buffers")

        # Create the buffer manager
        buffer_manager = BufferManager(placements, tags, txrx)

        for placement in progress.over(placements.placements):
            if isinstance(placement.vertex, AbstractSendsBuffersFromHost):
                if placement.vertex.buffering_input():
                    buffer_manager.add_sender_vertex(placement.vertex)

            if isinstance(placement.vertex, AbstractReceiveBuffersToHost):
                buffer_manager.add_receiving_vertex(placement.vertex)

        return buffer_manager
