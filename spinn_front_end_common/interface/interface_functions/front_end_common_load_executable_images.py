"""

"""

# pacman imports
from pacman.utilities.utility_objs.progress_bar import ProgressBar

# spinnman imports
from spinnman.data.file_data_reader import FileDataReader \
    as SpinnmanFileDataReader

# front end commom imports
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions

# general imports
import logging
import os

logger = logging.getLogger(__name__)


class FrontEndCommomLoadExecutableImages(object):
    """
    FrontEndCommomLoadExecutableImages
    """

    def __call__(self, executable_targets, app_id, transciever):
        """ Go through the executable targets and load each binary to \
            everywhere and then send a start request to the cores that \
            actually use it
        """

        progress_bar = ProgressBar(executable_targets.total_processors,
                                   "Loading executables onto the machine")
        for executable_target_key in executable_targets.binary_paths():
            file_reader = SpinnmanFileDataReader(executable_target_key)
            core_subset = executable_targets.\
                retrieve_cores_for_a_executable_target(executable_target_key)

            statinfo = os.stat(executable_target_key)
            size = statinfo.st_size

            # TODO there is a need to parse the binary and see if its
            # ITCM and DTCM requirements are within acceptable params for
            # operating on spinnaker. Currnently there jsut a few safety
            # checks which may not be accurate enough.
            if size > constants.MAX_SAFE_BINARY_SIZE:
                logger.warn(
                    "The size of this binary is large enough that its"
                    " possible that the binary may be larger than what is"
                    " supported by spinnaker currently. Please reduce the"
                    " binary size if it starts to behave strangely, or goes"
                    " into the wdog state before starting.")
                if size > constants.MAX_POSSIBLE_BINARY_SIZE:
                    raise exceptions.ConfigurationException(
                        "The size of the binary is too large and therefore"
                        " will very likely cause a WDOG state. Until a more"
                        " precise measurement of ITCM and DTCM can be produced"
                        " this is deemed as an error state. Please reduce the"
                        " size of your binary or circumvent this error check.")

            transciever.execute_flood(core_subset, file_reader, app_id, size)

            acutal_cores_loaded = 0
            for chip_based in core_subset.core_subsets:
                for _ in chip_based.processor_ids:
                    acutal_cores_loaded += 1
            progress_bar.update(amount_to_add=acutal_cores_loaded)
        progress_bar.end()

        return {"LoadBinariesToken": True}

