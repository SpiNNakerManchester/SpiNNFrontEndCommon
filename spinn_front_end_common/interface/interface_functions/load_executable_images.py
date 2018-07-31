from spinn_utilities.progress_bar import ProgressBar

from spinnman.messages.scp.enums import Signal
from spinnman.model.enums import CPUState

# general imports
import logging

logger = logging.getLogger(__name__)


class LoadExecutableImages(object):
    """ Go through the executable targets and load each binary to everywhere\
        and then send a start request to the cores that actually use it.
    """

    __slots__ = []

    def __call__(self, executable_targets, app_id, transceiver):
        progress = ProgressBar(
            executable_targets.total_processors + 1,
            "Loading executables onto the machine")

        for binary in executable_targets.binaries:
            progress.update(self._launch_binary(
                executable_targets, binary, transceiver, app_id))

        self._start_simulation(executable_targets, transceiver, app_id)
        progress.update()
        progress.end()

    def _launch_binary(self, executable_targets, binary, txrx, app_id):
        core_subset = executable_targets.get_cores_for_binary(binary)
        txrx.execute_flood(
            core_subset, binary, app_id, wait=True, is_filename=True)
        return len(core_subset)

    def _start_simulation(self, executable_targets, txrx, app_id):
        txrx.wait_for_cores_to_be_in_state(
            executable_targets.all_core_subsets, app_id, [CPUState.READY])
        txrx.send_signal(app_id, Signal.START)
