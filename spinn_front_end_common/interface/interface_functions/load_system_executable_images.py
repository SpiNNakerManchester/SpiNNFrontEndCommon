from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_utilities.progress_bar import ProgressBar

# general imports
import logging

from spinnman.messages.scp.enums import Signal
from spinnman.model.enums import CPUState

logger = logging.getLogger(__name__)


class LoadSystemExecutableImages(object):
    __slots__ = []

    def __call__(self, executable_targets, app_id, transceiver):
        """ Go through the executable targets and load each binary to \
            everywhere and then send a start request to the cores that \
            actually use it
        """

        progress = ProgressBar(
            executable_targets.get_n_cores_for_executable_type(
                ExecutableType.SYSTEM),
            "Loading system executables onto the machine")

        for binary in executable_targets.get_binaries_of_executable_type(
                ExecutableType.SYSTEM):
            progress.update(
                helpful_functions.flood_fill_binary_to_spinnaker(
                    executable_targets, binary, transceiver, app_id))
            transceiver.wait_for_cores_to_be_in_state(
                executable_targets.get_cores_for_binary(binary), app_id,
                [CPUState.READY])
        transceiver.send_signal(app_id, Signal.START)
        progress.end()
