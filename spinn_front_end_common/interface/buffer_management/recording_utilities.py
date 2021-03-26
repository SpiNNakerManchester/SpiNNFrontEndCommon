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

from spinn_front_end_common.utilities.constants import (
    SARK_PER_MALLOC_SDRAM_USAGE, BYTES_PER_WORD)

# Size of data in the header for each recording region
# 1 word for space, 1 word for size+missing, 1 word for pointer
_PER_REGION_HEADER_SIZE = BYTES_PER_WORD * 3


def get_recording_header_size(n_recording_regions):
    """ Get the size of the data to be written for the recording header

    :param int n_recording_regions: The number of regions that can be recorded
    :rtype: int
    """
    # See recording.h/recording_initialise for data included in the header
    return BYTES_PER_WORD + (n_recording_regions * _PER_REGION_HEADER_SIZE)


def get_recording_data_constant_size(n_recording_regions):
    """ Get the size of the recorded data to be reserved that doesn't change

    :param int n_recording_regions: The number of regions that can be recorded
    :rtype: int
    """
    return (n_recording_regions * SARK_PER_MALLOC_SDRAM_USAGE)


def get_recording_header_array(recorded_region_sizes):
    """ Get data to be written for the recording header

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
