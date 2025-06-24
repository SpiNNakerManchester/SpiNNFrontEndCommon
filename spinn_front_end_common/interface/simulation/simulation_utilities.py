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

import os
from typing import List
from pacman.utilities.utility_calls import md5
from spinnman.model.enums import SDP_PORTS
from spinn_front_end_common.data import FecDataView


def get_simulation_header_array(binary_file_name: str) -> List[int]:
    """
    Get data to be written to the simulation header.

    :param binary_file_name: The name of the binary of the application
    :return: An array of values to be written as the simulation header
    """
    # Get first 32-bits of the md5 hash of the application name
    application_name_hash = md5(os.path.splitext(binary_file_name)[0])[:8]

    # Write this to the system region (to be picked up by the simulation):
    return [
        int(application_name_hash, 16),
        FecDataView.get_hardware_time_step_us(),
        # SDP port number for receiving synchronisations and new run times
        SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value]


def get_simulation_header_array_no_timestep(
        binary_file_name: str) -> List[int]:
    """
    Get data to be written to the simulation header.
    Use for binaries that do not want to know the system timestep.

    :param binary_file_name: The name of the binary of the application
    :return: An array of values to be written as the simulation header
    """
    # Get first 32-bits of the md5 hash of the application name
    application_name_hash = md5(os.path.splitext(binary_file_name)[0])[:8]

    # Write this to the system region (to be picked up by the simulation):
    return [
        int(application_name_hash, 16),
        0,
        # SDP port number for receiving synchronisations and new run times
        SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value]
