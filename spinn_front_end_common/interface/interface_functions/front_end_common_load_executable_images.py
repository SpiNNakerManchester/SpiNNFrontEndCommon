
# pacman imports
from spinn_machine.utilities.progress_bar import ProgressBar

# front end common imports
from spinn_front_end_common.utilities import exceptions

# general imports
import logging

logger = logging.getLogger(__name__)


class FrontEndCommonLoadExecutableImages(object):

    __slots__ = []

    def __call__(self, executable_targets, app_id, transceiver,
                 loaded_application_data_token, use_progress_bar=True):
        """ Go through the executable targets and load each binary to \
            everywhere and then send a start request to the cores that \
            actually use it
        """

        if not loaded_application_data_token:
            raise exceptions.ConfigurationException(
                "The token for having loaded the application data token is set"
                " to false and therefore I cannot run. Please fix and try "
                "again")

        progress_bar = None
        if use_progress_bar:
            progress_bar = ProgressBar(executable_targets.total_processors,
                                       "Loading executables onto the machine")

        for executable_target_key in executable_targets.binaries:
            core_subset = executable_targets.get_cores_for_binary(
                executable_target_key)

            transceiver.execute_flood(
                core_subset, executable_target_key, app_id)

            acutal_cores_loaded = 0
            for chip_based in core_subset.core_subsets:
                for _ in chip_based.processor_ids:
                    acutal_cores_loaded += 1
            if use_progress_bar:
                progress_bar.update(amount_to_add=acutal_cores_loaded)
        if use_progress_bar:
            progress_bar.end()

        return True
