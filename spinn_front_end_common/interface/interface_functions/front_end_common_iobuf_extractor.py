"""
FrontEndCommonIOBufExtractor
"""
from pacman.utilities.utility_objs.message_holder import MessageHolder
from spinn_machine.progress_bar import ProgressBar
from spinn_front_end_common.utilities import exceptions


class FrontEndCommonIOBufExtractor(object):
    """
    extracts iobuf from the stuff that's ran on the machine, and separates
    errors from the standard iobuf
    """

    def __call__(self, transceiver, has_ran, placements=None,
                 core_subsets=None, warning_messages=None):
        if not has_ran:
            raise exceptions.ConfigurationException(
                "The simulation needs to have tried to run before asking for"
                "iobuf. Please fix and try again")

        if core_subsets is not None:
            io_buffers, error_entries, warn_entries =\
                self._run_for_core_subsets(
                    core_subsets, transceiver, warning_messages)
        elif placements is not None:
            io_buffers, error_entries, warn_entries =\
                self._run_for_placements(
                    placements, transceiver, warning_messages)
        else:
            raise exceptions.ConfigurationException(
                "The FrontEndCommonIOBufExtractor requires either a placements"
                " object or a core sets object to be able to execute. Please"
                " fix and try again.")
        return {'io_buffers': io_buffers,
                'error_entries': error_entries,
                'warn_entries': warn_entries}

    def _run_for_core_subsets(
            self, core_subsets, transceiver, warning_messages):
        progress_bar = ProgressBar(len(core_subsets),
                                   "Extracting IOBUF from failed cores")
        error_entries = MessageHolder()
        if warning_messages is not None:
            warn_entries = warning_messages
        else:
            warn_entries = MessageHolder()
        io_buffers = list(transceiver.get_iobuf(core_subsets))
        for io_buffer in io_buffers:
            self._check_iobuf_for_error(io_buffer, error_entries, warn_entries)
            progress_bar.update()
        progress_bar.end()
        return io_buffers, error_entries, warn_entries

    def _run_for_placements(
            self, placements, transceiver, warning_messages):
        io_buffers = list()
        error_entries = MessageHolder()
        if warning_messages is not None:
            warn_entries = warning_messages
        else:
            warn_entries = MessageHolder()
        progress_bar = ProgressBar(len(placements),
                                   "Extracting IOBUF from all cores")
        for placement in placements:
            iobuf = transceiver.get_iobuf_from_core(
                placement.x, placement.y, placement.p)
            io_buffers.append(iobuf)
            self._check_iobuf_for_error(iobuf, error_entries, warn_entries)
            progress_bar.update()
        progress_bar.end()
        return io_buffers, error_entries, warn_entries

    def _check_iobuf_for_error(self, iobuf, error_entries, warn_entries):
        lines = iobuf.iobuf.split("\n")
        for line in lines:
            line = line.encode('ascii', 'ignore')
            bits = line.split("[ERROR]")
            if len(bits) != 1:
                self._convert_line_bits(bits, iobuf, error_entries)
            bits = line.split("[WARNING]")
            if len(bits) != 1:
                self._convert_line_bits(bits, iobuf, warn_entries)

    @staticmethod
    def _convert_line_bits(bits, iobuf, entries):
        error_line = bits[1]
        bits = error_line.split("):")
        entries.add_core_message(iobuf.x, iobuf.y, iobuf.p, bits[1], bits[0])
