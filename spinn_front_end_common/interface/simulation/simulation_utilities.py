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
from pacman.utilities.utility_calls import md5
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import SDP_PORTS


def get_simulation_header_array(binary_file_name):
    """
    Get data to be written to the simulation header.

    :param str binary_file_name: The name of the binary of the application
    :return: An array of values to be written as the simulation header
    :rtype: list(int)
    """
    # Get first 32-bits of the md5 hash of the application name
    application_name_hash = md5(os.path.splitext(binary_file_name)[0])[:8]

    # Write this to the system region (to be picked up by the simulation):
    data = list()
    data.append(int(application_name_hash, 16))
    data.append(FecDataView.get_hardware_time_step_us())

    # add SDP port number for receiving synchronisations and new run times
    data.append(SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value)

    return data


def get_simulation_header_array_no_timestep(binary_file_name):
    """
    Get data to be written to the simulation header.

    :param str binary_file_name: The name of the binary of the application
    :return: An array of values to be written as the simulation header
    :rtype: list(int)
    """
    # Get first 32-bits of the md5 hash of the application name
    application_name_hash = md5(os.path.splitext(binary_file_name)[0])[:8]

    # Write this to the system region (to be picked up by the simulation):
    data = list()
    data.append(int(application_name_hash, 16))
    data.append(0)

    # add SDP port number for receiving synchronisations and new run times
    data.append(SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value)

    return data
