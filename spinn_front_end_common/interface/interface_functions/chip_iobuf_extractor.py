from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.utilities.exceptions import ConfigurationException
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
            self, transceiver, has_ran, core_subsets, provenance_file_path):
        if not has_ran:
            raise ConfigurationException(
                "The simulation needs to have tried to run before asking for"
                "iobuf. Please fix and try again")

        return self._run_for_core_subsets(
            core_subsets, transceiver, provenance_file_path)

    def _run_for_core_subsets(
            self, core_subsets, transceiver, provenance_file_path):
        progress = ProgressBar(
            len(core_subsets), "Extracting IOBUF from the machine")
        error_entries = list()
        warn_entries = list()

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
            with open(file_name, mode) as writer:
                writer.write(iobuf.iobuf)

        # check iobuf for errors
        for io_buffer in progress.over(io_buffers):
            self._check_iobuf_for_error(io_buffer, error_entries, warn_entries)
        return error_entries, warn_entries

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
        match = regex.match(line)
        if match:
            entries.append("{}, {}, {}: {} ({})".format(
                x, y, p, match.group(ENTRY_TEXT), match.group(ENTRY_FILE)))
