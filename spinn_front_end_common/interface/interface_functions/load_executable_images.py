import logging
from spinn_utilities.progress_bar import ProgressBar
from spinnman.messages.scp.enums import Signal
from spinnman.model.enums import CPUState
from spinn_front_end_common.utilities.helpful_functions import (
    flood_fill_binary_to_spinnaker)
from spinn_front_end_common.utilities.utility_objs import (
    ExecutableType, ExecutableTargets)

logger = logging.getLogger(__name__)


class LoadExecutableImages(object):
    """ Go through the executable targets and load each binary to everywhere\
        and then send a start request to the cores that actually use it.
    """

    __slots__ = []

    def load_app_images(self, executable_targets, app_id, transceiver):
        self.__load_images(executable_targets, app_id, transceiver,
                           lambda ty: ty is not ExecutableType.SYSTEM,
                           "Loading executables onto the machine")

    def load_sys_images(self, executable_targets, app_id, transceiver):
        self.__load_images(executable_targets, app_id, transceiver,
                           lambda ty: ty is ExecutableType.SYSTEM,
                           "Loading system executables onto the machine")

    def __load_images(self, executable_targets, app_id, txrx, filt, label):
        # Compute what work is to be done here
        binaries, cores = self.__filter(executable_targets, filt)

        # ISSUE: Loading order may be non-constant on older Python
        progress = ProgressBar(cores.total_processors + 1, label)
        for binary in binaries:
            progress.update(flood_fill_binary_to_spinnaker(
                executable_targets, binary, txrx, app_id))

        self.__start_simulation(cores, txrx, app_id)
        progress.update()
        progress.end()

    @staticmethod
    def __filter(targets, filt):
        binaries = []
        cores = ExecutableTargets()
        for exe_type in targets.executable_types_in_binary_set():
            if filt(exe_type):
                for aplx in targets.get_binaries_of_executable_type(exe_type):
                    binaries.append(aplx)
                    cores.add_subsets(
                        aplx, targets.get_cores_for_binary(aplx), exe_type)
        return binaries, cores

    @staticmethod
    def __start_simulation(executable_targets, txrx, app_id):
        txrx.wait_for_cores_to_be_in_state(
            executable_targets.all_core_subsets, app_id, [CPUState.READY])
        txrx.send_signal(app_id, Signal.START)
