import logging
from spinn_front_end_common.utilities.helpful_functions import (
    flood_fill_binary_to_spinnaker)
from spinn_front_end_common.utilities.utility_objs.ExecutableType import (
    SYSTEM)
from spinn_utilities.progress_bar import ProgressBar
from spinnman.messages.scp.enums.Signal import START
from spinnman.model.enums.CPUState import READY

logger = logging.getLogger(__name__)


class LoadSystemExecutableImages(object):
    __slots__ = []

    def __call__(self, executable_targets, app_id, transceiver):
        """ Go through the executable targets and load each binary to\
            everywhere and then send a start request to the cores that\
            actually use it
        """

        progress = ProgressBar(
            executable_targets.get_n_cores_for_executable_type(SYSTEM),
            "Loading system executables onto the machine")
        self._launch_system_executables(
            transceiver, app_id, executable_targets, progress)
        progress.end()

    @staticmethod
    def _launch_system_executables(txrx, app_id, targets, progress=None):
        for binary in targets.get_binaries_of_executable_type(SYSTEM):
            n_loaded = flood_fill_binary_to_spinnaker(
                targets, binary, txrx, app_id)
            if progress is not None:
                progress.update(n_loaded)
            txrx.wait_for_cores_to_be_in_state(
                targets.get_cores_for_binary(binary), app_id, [READY])
        txrx.send_signal(app_id, START)
