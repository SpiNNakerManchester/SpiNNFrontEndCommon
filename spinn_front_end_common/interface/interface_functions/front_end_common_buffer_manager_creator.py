from spinn_machine.utilities.progress_bar import ProgressBar

from spinn_front_end_common.interface.buffer_management.buffer_manager import \
    BufferManager
from spinn_front_end_common.interface.buffer_management.buffer_models\
    .abstract_sends_buffers_from_host import AbstractSendsBuffersFromHost
from spinn_front_end_common.interface.buffer_management.buffer_models\
    .abstract_receive_buffers_to_host \
    import AbstractReceiveBuffersToHost


class FrontEndCommonBufferManagerCreator(object):

    def __call__(
            self, placements, tags, txrx, write_reload_files, app_data_folder):
        progress_bar = ProgressBar(
            len(list(placements.placements)), "Initialising buffers")

        # Create the buffer manager
        buffer_manager = BufferManager(
            placements, tags, txrx, write_reload_files, app_data_folder)

        for placement in placements.placements:
            if isinstance(
                    placement.subvertex,
                    AbstractSendsBuffersFromHost):
                if placement.subvertex.buffering_input():
                    buffer_manager.add_sender_vertex(placement.subvertex)

            if isinstance(placement.subvertex, AbstractReceiveBuffersToHost):
                if placement.subvertex.buffering_output():
                    buffer_manager.add_receiving_vertex(placement.subvertex)

            progress_bar.update()
        progress_bar.end()

        return {"buffer_manager": buffer_manager}
