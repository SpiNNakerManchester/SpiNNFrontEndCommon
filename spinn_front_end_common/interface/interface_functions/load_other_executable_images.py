import logging
from spinn_front_end_common.utilities.utility_objs.ExecutableType \
    import SYSTEM
from spinn_machine import CoreSubsets
from spinn_utilities.progress_bar import ProgressBar
from spinnman.messages.scp.enums.Signal import START
from spinnman.model.enums.CPUState import READY
from spinn_front_end_common.utilities.helpful_functions \
    import flood_fill_binary_to_spinnaker

logger = logging.getLogger(__name__)


class LoadOtherExecutableImages(object):
    __slots__ = []

    def __call__(self, executable_targets, app_id, transceiver):
        """ Go through the executable targets and load each binary to\
            everywhere and then send a start request to the cores that\
            actually use it
        """

        progress = ProgressBar(
            executable_targets.total_processors + 1 -
            executable_targets.get_n_cores_for_executable_type(SYSTEM),
            "Loading application executables onto the machine")

        user_core_subsets = self._load_user_executables(
            transceiver, app_id, executable_targets, progress)
        progress.update()
        self._start_simulation(transceiver, app_id, user_core_subsets)
        progress.end()

    @staticmethod
    def _load_user_executables(txrx, app_id, targets, progress=None):
        user_core_subsets = CoreSubsets()
        for exe_type in targets.executable_types_in_binary_set():
            # only load executables not of system type
            if exe_type == SYSTEM:
                continue
            for binary in targets.get_binaries_of_executable_type(exe_type):
                n_loaded = flood_fill_binary_to_spinnaker(
                    targets, binary, txrx, app_id)
                if progress is not None:
                    progress.update(n_loaded)
                user_core_subsets.add_core_subsets(
                    targets.get_cores_for_binary(binary))
        return user_core_subsets

    @staticmethod
    def _start_simulation(txrx, app_id, user_core_subsets):
        txrx.wait_for_cores_to_be_in_state(user_core_subsets, app_id, [READY])
        txrx.send_signal(app_id, START)
