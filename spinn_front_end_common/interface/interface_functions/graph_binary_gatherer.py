# Copyright (c) 2016 The University of Manchester
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
from spinnman.model import ExecutableTargets
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from pacman.model.graphs import AbstractVirtual
from pacman.model.placements import Placement
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import (
    ExecutableNotFoundException)
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary

logger = FormatAdapter(logging.getLogger(__name__))


def graph_binary_gatherer() -> ExecutableTargets:
    """
    Extracts binaries to be executed.

    :returns: The Executable targets loaded with the binaries
    """
    return _GraphBinaryGatherer().gather_binaries()


class _GraphBinaryGatherer(object):
    """
    Extracts binaries to be executed.
    """
    __slots__ = ("_exe_targets", )

    def __init__(self) -> None:
        self._exe_targets = ExecutableTargets()

    def gather_binaries(self) -> ExecutableTargets:
        """
        Gather the binary for each placement

        :returns: The Executable targets loaded with the binaries
        """
        progress = ProgressBar(
            FecDataView.get_n_placements(), "Finding binaries")
        for placement in progress.over(FecDataView.iterate_placemements()):
            self.__get_binary(placement)

        return self._exe_targets

    def __get_binary(self, placement: Placement) -> None:
        # if the vertex cannot be executed, ignore it
        vertex = placement.vertex
        if not isinstance(vertex, AbstractHasAssociatedBinary):
            if not isinstance(vertex, AbstractVirtual):
                logger.error(
                    "Vertex {} does not implement either "
                    "AbstractHasAssociatedBinary or AbstractVirtual. So it is "
                    "unclear if it should or should not have a binary", vertex)
            return

        # Get name of binary from vertex
        binary_name = vertex.get_binary_file_name()
        exec_type = vertex.get_binary_start_type()

        # Attempt to find this within search paths
        binary_path = FecDataView.get_executable_path(binary_name)
        if binary_path is None:
            raise ExecutableNotFoundException(binary_name)

        self._exe_targets.add_processor(
            binary_path, placement.x, placement.y, placement.p, exec_type)
