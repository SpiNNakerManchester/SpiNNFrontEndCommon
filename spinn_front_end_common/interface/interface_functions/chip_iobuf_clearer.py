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

from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.scp import ClearIOBUFProcess
from spinn_front_end_common.utilities.utility_objs import ExecutableType


def chip_io_buf_clearer():
    """
    Clears the logging output buffer of an application running on a
    SpiNNaker machine.
    """
    executable_types = FecDataView.get_executable_types()
    if ExecutableType.USES_SIMULATION_INTERFACE in executable_types:
        core_subsets = \
            executable_types[ExecutableType.USES_SIMULATION_INTERFACE]

        process = ClearIOBUFProcess(
            FecDataView.get_scamp_connection_selector())
        process.clear_iobuf(core_subsets, len(core_subsets))
