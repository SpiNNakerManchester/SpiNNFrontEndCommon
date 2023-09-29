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

from spinn_front_end_common.utilities.constants import (
    SARK_PER_MALLOC_SDRAM_USAGE, BYTES_PER_WORD)

# Size of data in the header for each recording region
# 1 word for space, 1 word for size+missing, 1 word for pointer
_PER_REGION_HEADER_SIZE = BYTES_PER_WORD * 3


def get_recording_header_size(n_recording_regions):
    """
    Get the size of the data to be written for the recording header.

    This is the data that sets up how recording will be done, and indicates the
    sizes of the regions to be stored.

    :param int n_recording_regions: The number of regions that can be recorded
    :rtype: int
    """
    # See recording.h/recording_initialise for data included in the header
    return BYTES_PER_WORD + (n_recording_regions * _PER_REGION_HEADER_SIZE)


def get_recording_data_constant_size(n_recording_regions):
    """
    Get the size of the headers that are stored in the SDRAM spaces
    allocated during recording_initialise, and so do not need to be
    reserved with DSG (but need to be accounted for in SDRAM calculations).

    :param int n_recording_regions: The number of regions that can be recorded
    :rtype: int
    """
    return (n_recording_regions * SARK_PER_MALLOC_SDRAM_USAGE)


def get_recording_header_array(recorded_region_sizes):
    """
    Get data to be written for the recording header.

    :param list(int) recorded_region_sizes:
        A list of sizes of each region to be recorded.
        A size of 0 is acceptable.
    :rtype: list(int)
    """

    # See recording.h/recording_initialise for data included in the header
    data = list()

    # The parameters
    data.append(len(recorded_region_sizes))

    # Add (space, size, pointer) for each region
    for space in recorded_region_sizes:
        data.extend([space, 0, 0])

    return data
