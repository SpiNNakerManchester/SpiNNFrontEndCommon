# Copyright (c) 2021 The University of Manchester
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

from spinn_utilities.exceptions import NotSetupException, DataNotYetAvialable
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import add_spinnaker_cfg
from spinn_utilities.config_holder import clear_cfg_files

# This can not be a unittest as the unitest suite would use the same
# python console and therefore the same singleton multiple times

# It can be run multiple time as each run is a new python console

# reset the configs without mocking the global data
clear_cfg_files(True)
add_spinnaker_cfg(board_type=None)

view = FecDataView()
try:
    a = FecDataView.get_simulation_time_step_us()
    raise NotImplementedError("OOPS")
except NotSetupException:
    pass
writer = FecDataWriter.setup()
try:
    FecDataView.get_simulation_time_step_us()
    raise NotImplementedError("OOPS")
except DataNotYetAvialable:
    pass
writer.set_up_timings(1000, 1)
print(FecDataView.get_simulation_time_step_us())
