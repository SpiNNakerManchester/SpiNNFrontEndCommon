
# pacman imports
from spinn_machine.utilities.progress_bar import ProgressBar

# front end common imports
from spinn_front_end_common.utilities import exceptions

# general imports
import logging
from spinnman.messages.scp.enums.scp_signal import SCPSignal
from spinnman.model.enums.cpu_state import CPUState

logger = logging.getLogger(__name__)


class FrontEndCommonLoadExecutableImages(object):

    __slots__ = []

    def __call__(self, executable_targets, app_id, transceiver,
                 loaded_application_data_token):
        """ Go through the executable targets and load each binary to \
            everywhere and then send a start request to the cores that \
            actually use it
        """

        if not loaded_application_data_token:
            raise exceptions.ConfigurationException(
                "The token for having loaded the application data token is set"
                " to false and therefore I cannot run. Please fix and try "
                "again")

        progress_bar = ProgressBar(
            executable_targets.total_processors + 1,
            "Loading executables onto the machine")

        transceiver.execute_application(executable_targets, app_id)

        for binary in executable_targets.binaries:
            core_subset = executable_targets.get_cores_for_binary(binary)
            transceiver.execute_flood(
                core_subset, binary, app_id, wait=True, is_filename=True)
            progress_bar.update(len(core_subset))

        transceiver.wait_for_cores_to_be_in_state(
            executable_targets.all_core_subsets, app_id, [CPUState.READY])
        transceiver.send_signal(app_id, SCPSignal.START)
        progress_bar.end()

        return True
