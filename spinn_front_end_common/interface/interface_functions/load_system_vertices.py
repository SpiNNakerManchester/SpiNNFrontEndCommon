from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_utilities.progress_bar import ProgressBar

from spinnman.messages.scp.enums import Signal
from spinnman.model.enums import CPUState

# general imports
import logging

logger = logging.getLogger(__name__)


class LoadSystemImages(object):
    __slots__ = []

    def __call__(self, executable_targets, app_id, transceiver):
        """ Go through the executable targets and load each binary to \
            everywhere and then send a start request to the cores that \
            actually use it
        """

        progress = ProgressBar(
            len(executable_targets.get_binaries_of_executable_type(
                ExecutableType.SYSTEM)),
            "Loading system executables onto the machine")

        for binary in executable_targets.get_binaries_of_executable_type(
                ExecutableType.SYSTEM):
            progress.update(self._launch_binary(
                executable_targets, binary, transceiver, app_id))

        progress.update()
        progress.end()

    @staticmethod
    def _launch_binary(executable_targets, binary, txrx, app_id):
        core_subset = executable_targets.get_cores_for_binary(binary)
        txrx.execute_flood(
            core_subset, binary, app_id, wait=True, is_filename=True)
        return len(core_subset)
