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

from collections.abc import Sized
import logging
import os
import re
from typing import (
    Iterable, List, Optional, Pattern, Sequence, Set, Tuple, TypeVar, Union)

from spinn_utilities.config_holder import get_config_str_or_none
from spinn_utilities.log import FormatAdapter
from spinn_utilities.make_tools.replacer import Replacer
from spinn_utilities.progress_bar import ProgressBar

from spinn_machine.core_subsets import CoreSubsets

from spinnman.model import ExecutableTargets
from spinnman.model.enums import ExecutableType
from spinnman.model.io_buffer import IOBuffer

from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.helpful_functions import (
    convert_string_into_chip_and_core_subset)


logger = FormatAdapter(logging.getLogger(__name__))
ERROR_ENTRY = re.compile(r"\[ERROR\]\s+\((.*)\):\s+(.*)")
WARNING_ENTRY = re.compile(r"\[WARNING\]\s+\((.*)\):\s+(.*)")
ENTRY_FILE = 1
ENTRY_TEXT = 2

#: :meta private:
T = TypeVar("T")


class _DummyProgress(object):
    """
    An alternative to the Progress bar so the over can be called.
    """

    def over(self, values: Iterable[T]) -> Iterable[T]:
        """
        Simple wrapper for the cases where a progress bar is being used
        to show progress through the iteration over a single collection.

        :param values: The base collection (any iterable) being iterated over
        :return: The passed in collection unchanged.
        """
        return values


class IOBufExtractor(object):
    """
    Extract the logging output buffers from the machine, and separates
    lines based on their prefix.
    """

    __slots__ = (
        "_filename_template", "_recovery_mode", "__system_binaries",
        "__app_path", "__sys_path", "__suppress_progress",
        "__from_cores", "__binary_types", "__executable_targets")

    def __init__(
            self, executable_targets: Optional[ExecutableTargets] = None, *,
            recovery_mode: bool = False,
            filename_template: str = (
                "iobuf_for_chip_{}_{}_processor_id_{}.txt"),
            suppress_progress: bool = False):
        """
        :param executable_targets:
            Which Binaries and core to extract from.
            `None` to extract from all.
        :param recovery_mode:
        :param filename_template:
        :param suppress_progress:
        """
        self._filename_template = filename_template
        self._recovery_mode = bool(recovery_mode)
        self.__suppress_progress = bool(suppress_progress)

        self.__app_path = FecDataView.get_app_provenance_dir_path()
        self.__sys_path = FecDataView.get_system_provenance_dir_path()
        self.__from_cores = get_config_str_or_none(
            "Reports", "extract_iobuf_from_cores")
        self.__binary_types = get_config_str_or_none(
            "Reports", "extract_iobuf_from_binary_types")
        if executable_targets is None:
            self.__executable_targets = FecDataView.get_executable_targets()
        else:
            self.__executable_targets = executable_targets

        self.__system_binaries: Set[str] = set()
        try:
            self.__system_binaries.update(
                self.__executable_targets.get_binaries_of_executable_type(
                    ExecutableType.SYSTEM))
        except KeyError:
            pass

    def extract_iobuf(self) -> Tuple[Sequence[str], Sequence[str]]:
        """
        Perform the extraction of IOBUF.

        :return: error_entries, warn_entries
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

    def __progress(self, bins: Sized) -> Union[ProgressBar, _DummyProgress]:
        if self.__suppress_progress:
            return _DummyProgress()
        label = (("Recovering" if self._recovery_mode else "Extracting")
                 + " IOBUF from the machine")
        return ProgressBar(len(bins), label)

    def __prov_path(self, binary: str) -> str:
        return (self.__sys_path if binary in self.__system_binaries
                else self.__app_path)

    def __extract_all_cores(self) -> Tuple[List[str], List[str]]:
        error_entries: List[str] = list()
        warn_entries: List[str] = list()
        # all the cores
        progress = self.__progress(self.__executable_targets.binaries)
        for binary in progress.over(self.__executable_targets.binaries):
            core_subsets = self.__executable_targets.get_cores_for_binary(
                binary)
            self.__extract_iobufs_for_binary(
                core_subsets, binary, error_entries, warn_entries)
        return error_entries, warn_entries

    def __extract_selected_cores_and_types(
            self) -> Tuple[List[str], List[str]]:
        error_entries: List[str] = list()
        warn_entries: List[str] = list()
        # bit of both
        assert self.__binary_types is not None
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

    def __extract_selected_cores(self) -> Tuple[List[str], List[str]]:
        error_entries: List[str] = list()
        warn_entries: List[str] = list()
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

    def __extract_selected_types(self) -> Tuple[List[str], List[str]]:
        error_entries: List[str] = list()
        warn_entries: List[str] = list()
        # some binaries
        assert self.__binary_types is not None
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
            self, core_subsets: CoreSubsets, binary: str,
            error_entries: List[str], warn_entries: List[str]) -> None:
        """
        :param core_subsets: Where the binary is deployed
        :param binary: What binary was deployed there.
            This is used to determine how to decompress the IOBUF output.
        :param error_entries:
        :param warn_entries:
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
            self, iobuf: IOBuffer, file_path: str, replacer: Replacer,
            error_entries: List[str], warn_entries: List[str]) -> None:
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

    def __recover_iobufs(self, core_subsets: CoreSubsets) -> List[IOBuffer]:
        io_buffers: List[IOBuffer] = []
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
    def __add_value_if_match(regex: Pattern, line: str,
                             entries: List[str], iobuf: IOBuffer) -> None:
        match = regex.match(line)
        if match:
            entries.append(f"{iobuf.x}, {iobuf.y}, {iobuf.p}: "
                           f"{match.group(ENTRY_TEXT)} "
                           f"({match.group(ENTRY_FILE)})")
