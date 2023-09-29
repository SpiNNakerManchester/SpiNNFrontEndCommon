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
from spinn_front_end_common.utilities.helpful_functions import (
    locate_memory_region_for_placement)
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD
from spinn_front_end_common.data import FecDataView
from .profile_data import ProfileData

_PROFILE_HEADER_SIZE_BYTES = BYTES_PER_WORD
_SIZE_OF_PROFILE_DATA_ENTRY_IN_BYTES = 2 * BYTES_PER_WORD
_BYTE_OFFSET_OF_PROFILE_DATA_IN_PROFILE_REGION = BYTES_PER_WORD


def get_profile_region_size(n_samples):
    """
    Get the size of the region of the profile data.

    :param int n_samples: number of different samples to record
    :return: the size in bytes used by the profile region
    :rtype: int
    """
    return _PROFILE_HEADER_SIZE_BYTES + (
        n_samples * _SIZE_OF_PROFILE_DATA_ENTRY_IN_BYTES)


def reserve_profile_region(spec, region, n_samples):
    """
    Reserves the profile region for recording the profile data.

    :param ~data_specification.DataSpecificationGenerator spec:
        the DSG specification writer
    :param int region: region ID for the profile data
    :param int n_samples: number of elements being sampled
    """
    size = get_profile_region_size(n_samples)
    spec.reserve_memory_region(
        region=region, size=size, label="profilerRegion")


def write_profile_region_data(spec, region, n_samples):
    """
    Writes the profile region data.

    :param ~data_specification.DataSpecificationGenerator spec:
        the DSG specification writer
    :param int region: region ID for the profile data
    :param int n_samples: number of elements being sampled
    """
    spec.switch_write_focus(region)
    spec.write_value(n_samples)


def get_profiling_data(profile_region, tag_labels, placement):
    """
    Utility function to get profile data from a profile region.

    :param int profile_region: DSG region to get profiling data out of SDRAM
    :param list(str) tag_labels: labels for the profiling data
    :param ~pacman.model.placements.Placement placement: placement
    :rtype: ProfileData
    """
    txrx = FecDataView.get_transceiver()
    profile_data = ProfileData(tag_labels)

    address = locate_memory_region_for_placement(
        placement=placement, region=profile_region)

    # Read the profiling data size
    words_written = txrx.read_word(placement.x, placement.y, address)

    # Read the profiling data
    if words_written != 0:
        address += _BYTE_OFFSET_OF_PROFILE_DATA_IN_PROFILE_REGION
        profile_data.add_data(txrx.read_memory(
            placement.x, placement.y, address, words_written * BYTES_PER_WORD))

    return profile_data
