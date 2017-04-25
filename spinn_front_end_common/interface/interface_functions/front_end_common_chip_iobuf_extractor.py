from spinn_machine.utilities.progress_bar import ProgressBar
from spinn_front_end_common.utilities import exceptions
import re


ERROR_ENTRY = re.compile("\[ERROR\]\s+\((.*)\):\s+(.*)")
WARNING_ENTRY = re.compile("\[WARNING\]\s+\((.*)\):\s+(.*)")
ENTRY_FILE = 1
ENTRY_TEXT = 2


class FrontEndCommonChipIOBufExtractor(object):
    """ Extract iobuf buffers from the machine, and separates lines based on\
        their prefix
    """

    __slots__ = []

    def __call__(self, transceiver, has_ran, core_subsets=None):

        if not has_ran:
            raise exceptions.ConfigurationException(
                "The simulation needs to have tried to run before asking for"
                "iobuf. Please fix and try again")

        if core_subsets is not None:
            io_buffers, error_entries, warn_entries =\
                self._run_for_core_subsets(core_subsets, transceiver)
        else:
            raise exceptions.ConfigurationException(
                "The FrontEndCommonIOBufExtractor requires a core sets "
                "object to be able to execute")

        return io_buffers, error_entries, warn_entries

    def _run_for_core_subsets(self, core_subsets, transceiver):
        progress_bar = ProgressBar(
            len(core_subsets), "Extracting IOBUF from the machine")
        error_entries = list()
        warn_entries = list()

        # extract iobuf
        io_buffers = list(transceiver.get_iobuf(core_subsets))

        # check iobuf for errors
        for io_buffer in io_buffers:
            self._check_iobuf_for_error(io_buffer, error_entries, warn_entries)
            progress_bar.update()
        progress_bar.end()
        return io_buffers, error_entries, warn_entries

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
