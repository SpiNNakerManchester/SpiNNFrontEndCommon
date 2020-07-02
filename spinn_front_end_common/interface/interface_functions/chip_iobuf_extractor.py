# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import os
import re

from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_utilities.log import FormatAdapter
from spinn_utilities.make_tools.replacer import Replacer
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.utilities.helpful_functions import (
    convert_string_into_chip_and_core_subset)
from spinn_machine.core_subsets import CoreSubsets
from spinnman.model.io_buffer import IOBuffer

logger = FormatAdapter(logging.getLogger(__name__))
ERROR_ENTRY = re.compile(r"\[ERROR\]\s+\((.*)\):\s+(.*)")
WARNING_ENTRY = re.compile(r"\[WARNING\]\s+\((.*)\):\s+(.*)")
ENTRY_FILE = 1
ENTRY_TEXT = 2

RECOVERING_LABEL = "Recovering IOBUF from the machine"
EXTRACTING_LABEL = "Extracting IOBUF from the machine"
FILE_FORMAT = "iobuf_for_chip_{}_{}_processor_id_{}.txt"


class _DummyProgress(object):
    def over(self, values):
        return values


class ChipIOBufExtractor(object):
    """ Extract the logging output buffers from the machine, and separates\
        lines based on their prefix.

    :param ~spinnman.transceiver.Transceiver transceiver:
    :param ExecutableTargets executable_targets:
    :param ExecutableFinder executable_finder:
    :param str app_provenance_file_path:
    :param str system_provenance_file_path:
    :param dict(str,ExecutableType) binary_executable_types:
    :param str from_cores:
    :param str binary_types:
    :return: error_entries, warn_entries
    :rtype: tuple(list(str),list(str))
    """

    __slots__ = [
        # Possible path to write application vertex output to
        "__app_path",
        # Template for the file names to be used where writing the results
        "__filename_template",
        # Flag to say this is after an an exception so don't throw new ones
        "__recovery_mode",
        # Flag to say no progress bar should be used/shown
        "__suppress_progress",
        # Possible path to write system vertex output to
        "__sys_path",
        # Binaries of type SYSTEM
        "__system_binaries",
        # Transceiver object to retreive data
        "__transceiver",
    ]

    def __init__(
            self, recovery_mode=False, filename_template=FILE_FORMAT,
            suppress_progress=False):
        """
        :param bool recovery_mode:
        :param str filename_template:
        """
        self.__filename_template = filename_template
        self.__recovery_mode = bool(recovery_mode)
        self.__system_binaries = {}
        self.__suppress_progress = bool(suppress_progress)

    def __call__(
            self, transceiver, executable_targets, executable_finder,
            app_provenance_file_path=None, system_provenance_file_path=None,
            from_cores="ALL", binary_types=None):
        """
        :param ~.Transceiver transceiver:
        :param ExecutableTargets executable_targets:
        :param ExecutableFinder executable_finder:
        :param app_provenance_file_path:
        :type app_provenance_file_path: str or None
        :param system_provenance_file_path:
        :type system_provenance_file_path: str or None
        :param dict(str,ExecutableType) binary_executable_types:
        :param str from_cores:
        :param str binary_types:
        :return: error_entries, warn_entries
        :rtype: tuple(list(str),list(str))
        """
        self.__app_path = app_provenance_file_path
        self.__sys_path = system_provenance_file_path
        self.__transceiver = transceiver
        self.__system_binaries = {}
        try:
            self.__system_binaries = executable_targets.\
                get_binaries_of_executable_type(ExecutableType.SYSTEM)
        except KeyError:
            pass

        # all the cores
        if from_cores == "ALL":
            return self.__extract_all_cores(executable_targets)
        elif from_cores:
            if binary_types:
                return self.__extract_selected_cores_and_types(
                    executable_targets, executable_finder, binary_types,
                    from_cores)
            else:
                return self.__extract_selected_cores(
                    executable_targets, from_cores)
        else:
            if binary_types:
                return self.__extract_selected_types(
                    executable_targets, executable_finder, binary_types)
            else:
            # nothing
                return [], []

    def __progress(self, bins):
        """
        :param list bins:
        :rtype: ~.ProgressBar
        """
        if self.__suppress_progress:
            return _DummyProgress()
        if self.__recovery_mode:
            return ProgressBar(len(bins), RECOVERING_LABEL)
        return ProgressBar(len(bins), EXTRACTING_LABEL)

    def __prov_path(self, binary):
        """
        :param str binary:
        :return: provenance directory path
        :rtype: str
        """
        return (self.__sys_path if binary in self.__system_binaries
                else self.__app_path)

    def __extract_all_cores(self, executable_targets):
        """
        :param ExecutableTargets executable_targets:
        :rtype: tuple(list(str), list(str))
        """
        error_entries = list()
        warn_entries = list()
        progress = self.__progress(executable_targets.binaries)
        with Replacer() as replacer:
            for binary in progress.over(executable_targets.binaries):
                core_subsets = executable_targets.get_cores_for_binary(binary)
                self.__extract_iobufs_for_binary(
                    core_subsets, replacer, binary, error_entries, warn_entries)
        return error_entries, warn_entries

    def __extract_selected_cores_and_types(
            self, executable_targets, executable_finder, binary_types,
            from_cores):
        """
        :param ExecutableTargets executable_targets:
        :param ExecutableFinder executable_finder:
        :param str binary_types:
        :param str from_cores:
        :rtype: tuple(list(str), list(str))
        """
        error_entries = list()
        warn_entries = list()
        # bit of both
        progress = self.__progress(executable_targets.binaries)
        binaries = executable_finder.get_executable_paths(binary_types)
        iocores = convert_string_into_chip_and_core_subset(from_cores)
        with Replacer() as replacer:
            for binary in progress.over(executable_targets.binaries):
                if binary in binaries:
                    core_subsets = \
                        executable_targets.get_cores_for_binary(binary)
                else:
                    core_subsets = iocores.intersect(
                        executable_targets.get_cores_for_binary(binary))
                if core_subsets:
                     self.__extract_iobufs_for_binary(
                        core_subsets, replacer, binary, error_entries,
                        warn_entries)
        return error_entries, warn_entries

    def __extract_selected_cores(
            self, executable_targets, from_cores):
        """
        :param ExecutableTargets executable_targets:
        :param str from_cores:
        :rtype: tuple(list(str), list(str))
        """
        error_entries = list()
        warn_entries = list()
        # some hard coded cores
        progress = self.__progress(executable_targets.binaries)
        iocores = convert_string_into_chip_and_core_subset(from_cores)
        with Replacer() as replacer:
            for binary in progress.over(executable_targets.binaries):
                core_subsets = iocores.intersect(
                    executable_targets.get_cores_for_binary(binary))
                if core_subsets:
                    self.__extract_iobufs_for_binary(
                        core_subsets, replacer, binary, error_entries,
                        warn_entries)
        return error_entries, warn_entries

    def __extract_selected_types(
            self, executable_targets, executable_finder, binary_types):
        """
        :param ExecutableTargets executable_targets:
        :param ExecutableFinder executable_finder:
        :param str binary_types:
        :rtype: tuple(list(str), list(str))
        """
        error_entries = list()
        warn_entries = list()
        # some binaries
        binaries = executable_finder.get_executable_paths(binary_types)
        progress = self.__progress(binaries)
        with Replacer() as replacer:
            for binary in progress.over(binaries):
                core_subsets = executable_targets.get_cores_for_binary(
                    binary)
                self.__extract_iobufs_for_binary(
                    core_subsets, replacer, binary, error_entries,
                    warn_entries)
        return error_entries, warn_entries

    def __extract_iobufs_for_binary(
            self, core_subsets, replacer, binary, error_entries, warn_entries):
        """
        :param ~.CoreSubsets core_subsets: Where the binary is deployed
        :param ~.Replacer replacer: Open object to handle log replacing
        :param str binary: What binary was deployed there.
            This is used to determine how to decompress the IOBUF output.
        :param list(str) error_entries:
        :param list(str) warn_entries:
        """
        prov_path = self.__prov_path(binary)
        # extract iobuf
        if self.__recovery_mode:
            io_buffers = self.__recover_iobufs(core_subsets)
        else:
            io_buffers = list(self.__transceiver.get_iobuf(core_subsets))

            # write iobuf
            for iobuf in io_buffers:
                self.__process_one_iobuf(iobuf, prov_path, replacer,
                                         error_entries, warn_entries)

    def __process_one_iobuf(
            self, iobuf, file_path, replacer, error_entries, warn_entries):
        """
        :param ~.IOBuffer iobuf:
        :param str file_path:
        :param ~.Replacer replacer:
        :param list(str) error_entries:
        :param list(str) warn_entries:
        """
        file_name = os.path.join(
            file_path, self.__filename_template.format(
                iobuf.x, iobuf.y, iobuf.p))

        # set mode of the file based off if the file already exists
        mode = "a" if os.path.exists(file_name) else "w"

        # write iobuf to file and call out errors and warnings.
        with open(file_name, mode) as f:
            for line in iobuf.iobuf.split("\n"):
                replaced = replacer.replace(line)
                f.write(replaced)
                f.write("\n")
                self.__add_value_if_match(
                    ERROR_ENTRY, replaced, error_entries, iobuf)
                self.__add_value_if_match(
                    WARNING_ENTRY, replaced, warn_entries, iobuf)

    def __recover_iobufs(self, core_subsets):
        """
        :param ~.CoreSubsets core_subsets:
        :rtype: list(~.IOBuffer)
        """
        io_buffers = []
        for core_subset in core_subsets:
            for p in core_subset.processor_ids:
                cs = CoreSubsets()
                cs.add_processor(core_subset.x, core_subset.y, p)
                try:
                    io_buffers.extend(self.__transceiver.get_iobuf(cs))
                except Exception as e:  # pylint: disable=broad-except
                    io_buffers.append(IOBuffer(
                        core_subset.x, core_subset.y, p,
                        "failed to retrieve iobufs from {},{},{}; {}".format(
                            core_subset.x, core_subset.y, p, str(e))))
        return io_buffers

    @staticmethod
    def __add_value_if_match(regex, line, entries, iobuf):
        """
        :param ~typing.Pattern regex:
        :param str line:
        :param list(str) entries:
        :param ~.IOBuffer iobuf:
        """
        match = regex.match(line)
        if match:
            entries.append("{}, {}, {}: {} ({})".format(
                iobuf.x, iobuf.y, iobuf.p, match.group(ENTRY_TEXT),
                match.group(ENTRY_FILE)))
