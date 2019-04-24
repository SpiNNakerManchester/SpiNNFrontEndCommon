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

    def __call__(self, executable_targets, app_id, transceiver):
        # Compute what work is to be done here
        binaries, cores = self.__filter(executable_targets)

        # ISSUE: Loading order may be non-constant on older Python
        progress = ProgressBar(cores.total_processors + 1,
                               self._progress_bar_label())
        for binary in binaries:
            progress.update(flood_fill_binary_to_spinnaker(
                executable_targets, binary, transceiver, app_id))

        self._start_simulation(cores, transceiver, app_id)
        progress.update()
        progress.end()

    def _progress_bar_label(self):
        return "Loading executables onto the machine"

    def __filter(self, targets):
        binaries = []
        cores = ExecutableTargets()
        for exe_type in targets.executable_types_in_binary_set():
            if self._filter_type(exe_type):
                for aplx in targets.get_binaries_of_executable_type(exe_type):
                    binaries.append(aplx)
                    cores.add_subsets(
                        aplx, targets.get_cores_for_binary(aplx), exe_type)
        return binaries, cores

    def _filter_type(self, executable_type):
        return executable_type is not ExecutableType.SYSTEM

    def _start_simulation(self, executable_targets, txrx, app_id):
        txrx.wait_for_cores_to_be_in_state(
            executable_targets.all_core_subsets, app_id, [CPUState.READY])
        txrx.send_signal(app_id, Signal.START)
