"""
FrontEndCommonIOBufExtractor
"""
from pacman.utilities.utility_objs.progress_bar import ProgressBar
from spinn_front_end_common.utilities import exceptions


class FrontEndCommonIOBufExtractor(object):
    """
    extracts iobuf from the stuff that's ran on the machine, and separates
    errors from the standard iobuf
    """

    def __call__(self, transceiver, has_ran, placements=None,
                 core_subsets=None):
        if not has_ran:
            raise exceptions.ConfigurationException(
                "The simulation needs to have tried to run before asking for"
                "iobuf. Please fix and try again")

        if placements is None and core_subsets is not None:
            io_buffers, error_entries =\
                self._run_for_core_subsets(core_subsets, transceiver)
        elif placements is not None and core_subsets is None:
            io_buffers, error_entries =\
                self._run_for_placements(placements, transceiver)
        else:
            raise exceptions.ConfigurationException(
                "The FrontEndCommonIOBufExtractor requires either a placements"
                " object or a core sets object to be able to execute. Please"
                " fix and try again.")
        return {'io_buffers': io_buffers,
                'error_entries': error_entries}

    def _run_for_core_subsets(self, core_subsets, transceiver):
        progress_bar = ProgressBar(len(core_subsets),
                                   "Extracting IOBUF from failed cores")
        error_entries = dict()
        io_buffers = list(transceiver.get_iobuf(core_subsets))
        for io_buffer in io_buffers:
            self._check_iobuf_for_error(io_buffer, error_entries)
            progress_bar.update()
        progress_bar.end()
        return io_buffers, error_entries

    def _run_for_placements(self, placements, transceiver):
        io_buffers = list()
        error_entries = dict()
        progress_bar = ProgressBar(len(placements),
                                   "Extracting IOBUF from all cores")
        for placement in placements:
            iobuf = transceiver.get_iobuf_from_core(
                placement.x, placement.y, placement.p)
            io_buffers.append(iobuf)
            self._check_iobuf_for_error(iobuf, error_entries)
            progress_bar.update()
        progress_bar.end()
        return io_buffers, error_entries

    @staticmethod
    def _check_iobuf_for_error(iobuf, error_entries):
        lines = iobuf.iobuf.split("\n")
        for line in lines:
            line = line.encode('ascii', 'ignore')
            bits = line.split("[ERROR]")
            if len(bits) != 1:
                error_line = bits[1]
                bits = error_line.split("):")
                error_final_line = bits[1] + ":" + bits[0]
                if (iobuf.x, iobuf.y, iobuf.p) not in error_entries:
                    error_entries[(iobuf.x, iobuf.y, iobuf.p)] = list()
                error_entries[(iobuf.x, iobuf.y, iobuf.p)].append(
                    error_final_line)
