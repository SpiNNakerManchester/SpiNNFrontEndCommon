from spinn_machine.utilities.progress_bar import ProgressBar

from spinn_front_end_common.utilities import exceptions


class FrontEndCommonIOBufExtractor(object):
    """ Extract iobuf buffers from the machine, and separates lines based on\
        their prefix
    """

    __slots__ = []

    def __call__(
            self, transceiver, has_ran, placements=None, core_subsets=None):

        if not has_ran:
            raise exceptions.ConfigurationException(
                "The simulation needs to have tried to run before asking for"
                "iobuf. Please fix and try again")

        if core_subsets is not None:
            io_buffers, error_entries, warn_entries =\
                self._run_for_core_subsets(
                    core_subsets, transceiver)
        elif placements is not None:
            io_buffers, error_entries, warn_entries =\
                self._run_for_placements(
                    placements, transceiver)
        else:
            raise exceptions.ConfigurationException(
                "The FrontEndCommonIOBufExtractor requires either a placements"
                " object or a core sets object to be able to execute")

        return io_buffers, error_entries, warn_entries

    def _run_for_core_subsets(self, core_subsets, transceiver):
        progress_bar = ProgressBar(len(core_subsets), "Extracting IOBUF")
        error_entries = list()
        warn_entries = list()
        io_buffers = list(transceiver.get_iobuf(core_subsets))
        for io_buffer in io_buffers:
            self._check_iobuf_for_error(io_buffer, error_entries, warn_entries)
            progress_bar.update()
        progress_bar.end()
        return io_buffers, error_entries, warn_entries

    def _run_for_placements(self, placements, transceiver):
        io_buffers = list()
        error_entries = list()
        warn_entries = list()
        progress_bar = ProgressBar(len(placements), "Extracting IOBUF")
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
        entries.append("{}, {}, {}: {} ({})".format(
            iobuf.x, iobuf.y, iobuf.p, bits[1], bits[0]))
