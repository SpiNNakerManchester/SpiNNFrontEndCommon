# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import re
from spinn_utilities.log import FormatAdapter
from spinn_utilities.make_tools.replacer import Replacer
from spinn_utilities.progress_bar import ProgressBar
from spinn_machine.core_subsets import CoreSubsets
from spinnman.model.io_buffer import IOBuffer
from spinn_utilities.config_holder import get_config_str
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.helpful_functions import (
    convert_string_into_chip_and_core_subset)


logger = FormatAdapter(logging.getLogger(__name__))
ERROR_ENTRY = re.compile(r"\[ERROR\]\s+\((.*)\):\s+(.*)")
WARNING_ENTRY = re.compile(r"\[WARNING\]\s+\((.*)\):\s+(.*)")
ENTRY_FILE = 1
ENTRY_TEXT = 2


class _DummyProgress(object):
    def over(self, values):
        return values


class IOBufExtractor(object):
    """
    Extract the logging output buffers from the machine, and separates
    lines based on their prefix.
    """

    __slots__ = ["_filename_template", "_recovery_mode", "__system_binaries",
                 "__app_path", "__sys_path",
                 "__suppress_progress", "__from_cores", "__binary_types",
                 "__executable_targets"]

    def __init__(self, executable_targets=None,
                 recovery_mode=False,
                 filename_template="iobuf_for_chip_{}_{}_processor_id_{}.txt",
                 suppress_progress=False):
        """
        :param bool recovery_mode:
        :param str filename_template:
        :param bool suppress_progress:
        :param executable_targets:
            Which Binaries and core to extract from.
            `None` to extract from all.
        :type executable_targets: ~spinnman.model.ExecutableTargets or None
        :param str from_cores:
        :param str binary_types:
        """
        self._filename_template = filename_template
        self._recovery_mode = bool(recovery_mode)
        self.__suppress_progress = bool(suppress_progress)

        self.__app_path = FecDataView.get_app_provenance_dir_path()
        self.__sys_path = FecDataView.get_system_provenance_dir_path()
        self.__from_cores = get_config_str(
            "Reports", "extract_iobuf_from_cores")
        self.__binary_types = get_config_str(
            "Reports", "extract_iobuf_from_binary_types")
        if executable_targets is None:
            self.__executable_targets = FecDataView.get_executable_targets()
        else:
            self.__executable_targets = executable_targets

        self.__system_binaries = set()
        try:
            self.__system_binaries.update(
                self.__executable_targets.get_binaries_of_executable_type(
                    ExecutableType.SYSTEM))
        except KeyError:
            pass

    def extract_iobuf(self):
        """
        Perform the extraction of IOBUF.

        :return: error_entries, warn_entries
        :rtype: tuple(list(str),list(str))
        """
        if self.__from_cores == "ALL":
            return self.__extract_all_cores()
        elif self.__from_cores and self.__binary_types:
            return self.__extract_selected_cores_and_types()
        elif self.__from_cores:
            return self.__extract_selected_cores()
        elif self.__binary_types:
            return self.__extract_selected_types()
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
        label = (("Recovering" if self._recovery_mode else "Extracting")
                 + " IOBUF from the machine")
        return ProgressBar(len(bins), label)

    def __prov_path(self, binary):
        """
        :param str binary:
        :return: provenance directory path
        :rtype: str
        """
        return (self.__sys_path if binary in self.__system_binaries
                else self.__app_path)

    def __extract_all_cores(self):
        """
        :rtype: tuple(list(str), list(str))
        """
        error_entries = list()
        warn_entries = list()
        # all the cores
        progress = self.__progress(self.__executable_targets.binaries)
        for binary in progress.over(self.__executable_targets.binaries):
            core_subsets = self.__executable_targets.get_cores_for_binary(
                binary)
            self.__extract_iobufs_for_binary(
                core_subsets, binary, error_entries, warn_entries)
        return error_entries, warn_entries

    def __extract_selected_cores_and_types(self):
        """
        :rtype: tuple(list(str), list(str))
        """
        error_entries = list()
        warn_entries = list()
        # bit of both
        progress = self.__progress(self.__executable_targets.binaries)
        binaries = FecDataView.get_executable_paths(self.__binary_types)
        iocores = convert_string_into_chip_and_core_subset(self.__from_cores)
        for binary in progress.over(self.__executable_targets.binaries):
            if binary in binaries:
                core_subsets = self.__executable_targets.get_cores_for_binary(
                    binary)
            else:
                core_subsets = iocores.intersect(
                    self.__executable_targets.get_cores_for_binary(binary))
            if core_subsets:
                self.__extract_iobufs_for_binary(
                    core_subsets, binary, error_entries, warn_entries)
        return error_entries, warn_entries

    def __extract_selected_cores(self):
        """
        :rtype: tuple(list(str), list(str))
        """
        error_entries = list()
        warn_entries = list()
        # some hard coded cores
        progress = self.__progress(self.__executable_targets.binaries)
        iocores = convert_string_into_chip_and_core_subset(self.__from_cores)
        for binary in progress.over(self.__executable_targets.binaries):
            core_subsets = iocores.intersect(
                self.__executable_targets.get_cores_for_binary(binary))
            if core_subsets:
                self.__extract_iobufs_for_binary(
                    core_subsets, binary, error_entries, warn_entries)
        return error_entries, warn_entries

    def __extract_selected_types(self):
        """
        :rtype: tuple(list(str), list(str))
        """
        error_entries = list()
        warn_entries = list()
        # some binaries
        binaries = FecDataView.get_executable_paths(self.__binary_types)
        progress = self.__progress(binaries)
        for binary in progress.over(binaries):
            core_subsets = self.__executable_targets.get_cores_for_binary(
                binary)
            if core_subsets is not None:
                self.__extract_iobufs_for_binary(
                    core_subsets, binary, error_entries, warn_entries)
        return error_entries, warn_entries

    def __extract_iobufs_for_binary(
            self, core_subsets, binary, error_entries, warn_entries):
        """
        :param ~.CoreSubsets core_subsets: Where the binary is deployed
        :param str binary: What binary was deployed there.
            This is used to determine how to decompress the IOBUF output.
        :param list(str) error_entries:
        :param list(str) warn_entries:
        """
        replacer = Replacer()
        prov_path = self.__prov_path(binary)

        # extract iobuf
        if self._recovery_mode:
            io_buffers = self.__recover_iobufs(core_subsets)
        else:
            io_buffers = list(FecDataView.get_transceiver().get_iobuf(
                core_subsets))

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
            file_path, self._filename_template.format(
                iobuf.x, iobuf.y, iobuf.p))

        # set mode of the file based off if the file already exists
        mode = "a" if os.path.exists(file_name) else "w"

        # write iobuf to file and call out errors and warnings.
        with open(file_name, mode, encoding="utf-8") as f:
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
                    transceiver = FecDataView.get_transceiver()
                    io_buffers.extend(transceiver.get_iobuf(cs))
                except Exception as e:  # pylint: disable=broad-except
                    io_buffers.append(IOBuffer(
                        core_subset.x, core_subset.y, p,
                        "failed to retrieve iobufs from "
                        f"{core_subset.x},{core_subset.y},{p}; "
                        f"{str(e)}"))
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
            entries.append(f"{iobuf.x}, {iobuf.y}, {iobuf.p}: "
                           f"{match.group(ENTRY_TEXT)} "
                           f"({match.group(ENTRY_FILE)})")
