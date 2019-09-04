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


class ChipIOBufExtractor(object):
    """ Extract the logging output buffers from the machine, and separates\
        lines based on their prefix.
    """

    __slots__ = ["_filename_template", "_recovery_mode"]

    def __init__(self, recovery_mode=False,
                 filename_template="iobuf_for_chip_{}_{}_processor_id_{}.txt"):
        self._filename_template = filename_template
        self._recovery_mode = bool(recovery_mode)

    def __call__(
            self, transceiver, executable_targets, executable_finder,
            app_provenance_file_path, system_provenance_file_path,
            binary_executable_types, from_cores="ALL", binary_types=None):

        error_entries = list()
        warn_entries = list()
        label = (("Recovering" if self._recovery_mode else "Extracting")
                 + " IOBUF from the machine")

        # all the cores
        if from_cores == "ALL":
            progress = ProgressBar(len(executable_targets.binaries), label)
            for binary in progress.over(executable_targets.binaries):
                core_subsets = executable_targets.get_cores_for_binary(binary)
                if (binary_executable_types[binary].value ==
                        ExecutableType.SYSTEM.value):
                    prov_path = system_provenance_file_path
                else:
                    prov_path = app_provenance_file_path
                self._run_for_core_subsets(
                    core_subsets, binary, transceiver, prov_path,
                    error_entries, warn_entries)

        elif from_cores:
            if binary_types:
                # bit of both
                progress = ProgressBar(len(executable_targets.binaries), label)
                binaries = executable_finder.get_executable_paths(binary_types)
                iocores = convert_string_into_chip_and_core_subset(from_cores)
                for binary in progress.over(executable_targets.binaries):
                    if binary in binaries:
                        core_subsets = executable_targets.get_cores_for_binary(
                            binary)
                    else:
                        core_subsets = iocores.intersect(
                            executable_targets.get_cores_for_binary(binary))
                    if core_subsets:
                        if (binary_executable_types[binary] ==
                                ExecutableType.SYSTEM):
                            prov_path = system_provenance_file_path
                        else:
                            prov_path = app_provenance_file_path
                        self._run_for_core_subsets(
                            core_subsets, binary, transceiver, prov_path,
                            error_entries, warn_entries)

            else:
                # some hard coded cores
                progress = ProgressBar(len(executable_targets.binaries), label)
                iocores = convert_string_into_chip_and_core_subset(from_cores)
                for binary in progress.over(executable_targets.binaries):
                    core_subsets = iocores.intersect(
                        executable_targets.get_cores_for_binary(binary))
                    if core_subsets:
                        if (binary_executable_types[binary] ==
                                ExecutableType.SYSTEM):
                            prov_path = system_provenance_file_path
                        else:
                            prov_path = app_provenance_file_path
                        self._run_for_core_subsets(
                            core_subsets, binary, transceiver, prov_path,
                            error_entries, warn_entries)
        else:
            if binary_types:
                # some binaries
                binaries = executable_finder.get_executable_paths(binary_types)
                progress = ProgressBar(len(binaries), label)
                for binary in progress.over(binaries):
                    core_subsets = executable_targets.get_cores_for_binary(
                        binary)
                    if (binary_executable_types[binary] ==
                            ExecutableType.SYSTEM):
                        prov_path = system_provenance_file_path
                    else:
                        prov_path = app_provenance_file_path
                    self._run_for_core_subsets(
                        core_subsets, binary, transceiver, prov_path,
                        error_entries, warn_entries)
            else:
                # nothing
                pass

        return error_entries, warn_entries

    def _run_for_core_subsets(
            self, core_subsets, binary, transceiver, provenance_file_path,
            error_entries, warn_entries):
        replacer = Replacer(binary)

        # extract iobuf
        if self._recovery_mode:
            io_buffers = self.__recover_iobufs(transceiver, core_subsets)
        else:
            io_buffers = list(transceiver.get_iobuf(core_subsets))

        # write iobuf
        for iobuf in io_buffers:
            file_name = os.path.join(
                provenance_file_path,
                self._filename_template.format(iobuf.x, iobuf.y, iobuf.p))

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

    def __recover_iobufs(self, transceiver, core_subsets):
        io_buffers = []
        for core_subset in core_subsets:
            for p in core_subset.processor_ids:
                cs = CoreSubsets()
                cs.add_processor(core_subset.x, core_subset.y, p)
                try:
                    io_buffers.extend(transceiver.get_iobuf(cs))
                except Exception as e:  # pylint: disable=broad-except
                    io_buffers.append(IOBuffer(
                        core_subset.x, core_subset.y, p,
                        "failed to retrieve iobufs from {},{},{}; {}".format(
                            core_subset.x, core_subset.y, p, str(e))))
        return io_buffers

    @staticmethod
    def __add_value_if_match(regex, line, entries, place):
        match = regex.match(line)
        if match:
            entries.append("{}, {}, {}: {} ({})".format(
                place.x, place.y, place.p, match.group(ENTRY_TEXT),
                match.group(ENTRY_FILE)))
