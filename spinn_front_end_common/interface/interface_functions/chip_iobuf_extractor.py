from spinn_utilities.make_tools.replacer import Replacer
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.utilities import helpful_functions
import re
import os


ERROR_ENTRY = re.compile("\[ERROR\]\s+\((.*)\):\s+(.*)")
WARNING_ENTRY = re.compile("\[WARNING\]\s+\((.*)\):\s+(.*)")
ENTRY_FILE = 1
ENTRY_TEXT = 2


class ChipIOBufExtractor(object):
    """ Extract iobuf buffers from the machine, and separates lines based on\
        their prefix
    """

    __slots__ = []

    def __call__(
            self, transceiver, executable_targets, executable_finder,
            provenance_file_path, from_cores="ALL", binary_types=None):

        error_entries = list()
        warn_entries = list()

        # all the cores
        if from_cores == "ALL":
            progress = ProgressBar(len(executable_targets.binaries),
                                   "Extracting IOBUF from the machine")
            for binary in progress.over(executable_targets.binaries):
                core_subsets = executable_targets.get_cores_for_binary(binary)
                self._run_for_core_subsets(
                    core_subsets, binary, transceiver, provenance_file_path,
                    error_entries, warn_entries)

        elif from_cores:
            if binary_types:
                # bit of both
                progress = ProgressBar(len(executable_targets.binaries),
                                       "Extracting IOBUF from the machine")
                binaries = executable_finder.get_executable_paths(binary_types)
                iocores = (helpful_functions.
                           convert_string_into_chip_and_core_subset(
                                from_cores))
                for binary in progress.over(executable_targets.binaries):
                    if binary in binaries:
                        core_subsets = executable_targets.get_cores_for_binary(
                            binary)
                    else:
                        core_subsets = iocores.intersect(
                            executable_targets.get_cores_for_binary(binary))
                    if core_subsets:
                        self._run_for_core_subsets(
                            core_subsets, binary, transceiver,
                            provenance_file_path, error_entries,
                            warn_entries)

            else:
                # some hard coded cores
                progress = ProgressBar(len(executable_targets.binaries),
                                       "Extracting IOBUF from the machine")
                iocores = (helpful_functions.
                           convert_string_into_chip_and_core_subset(
                                from_cores))
                for binary in progress.over(executable_targets.binaries):
                    core_subsets = iocores.intersect(
                        executable_targets.get_cores_for_binary(binary))
                    if core_subsets:
                        self._run_for_core_subsets(
                            core_subsets, binary, transceiver,
                            provenance_file_path, error_entries, warn_entries)
        else:
            if binary_types:
                # some binaries
                binaries = executable_finder.get_executable_paths(binary_types)
                progress = ProgressBar(len(binaries),
                                       "Extracting IOBUF from the machine")
                for binary in progress.over(binaries):
                    core_subsets = executable_targets.get_cores_for_binary(
                        binary)
                    self._run_for_core_subsets(
                        core_subsets, binary, transceiver,
                        provenance_file_path, error_entries, warn_entries)
            else:
                # nothing
                pass

        return error_entries, warn_entries

    def _run_for_core_subsets(
            self, core_subsets, binary, transceiver, provenance_file_path,
            error_entries, warn_entries):

        replacer = Replacer(binary)

        # extract iobuf
        io_buffers = list(transceiver.get_iobuf(core_subsets))

        # write iobuf
        for iobuf in io_buffers:
            file_name = os.path.join(
                provenance_file_path,
                "iobuf_for_chip_{}_{}_processor_id_{}.txt".format(
                    iobuf.x, iobuf.y, iobuf.p))

            # set mode of the file based off if the file already exists
            mode = "w"
            if os.path.exists(file_name):
                mode = "a"

            # write iobuf to file.
            with open(file_name, mode) as f:
                for line in iobuf.iobuf.split("\n"):
                    f.write(replacer.replace(line))
                    f.write("\n")
            self._check_iobuf_for_error(iobuf, error_entries, warn_entries)

    def _check_iobuf_for_error(self, iobuf, error_entries, warn_entries):
        lines = iobuf.iobuf.split("\n")
        for line in lines:
            line = line.encode('ascii', 'ignore')
            self._add_value_if_match(
                ERROR_ENTRY, line, error_entries, iobuf.x, iobuf.y, iobuf.p)
            self._add_value_if_match(
                WARNING_ENTRY, line, warn_entries, iobuf.x, iobuf.y, iobuf.p)

    @staticmethod
    def _add_value_if_match(regex, line, entries, x, y, p):
        # pylint: disable=too-many-arguments
        match = regex.match(line.decode('ascii'))
        if match:
            entries.append("{}, {}, {}: {} ({})".format(
                x, y, p, match.group(ENTRY_TEXT), match.group(ENTRY_FILE)))
