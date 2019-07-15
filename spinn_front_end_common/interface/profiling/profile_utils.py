import logging
import struct
from .profile_data import ProfileData
from spinn_front_end_common.utilities.helpful_functions import (
    locate_memory_region_for_placement)

logger = logging.getLogger(__name__)

PROFILE_HEADER_SIZE_BYTES = 4
SIZE_OF_PROFILE_DATA_ENTRY_IN_BYTES = 8
BYTE_OFFSET_OF_PROFILE_DATA_IN_PROFILE_REGION = 4
_ONE_WORD = struct.Struct("<I")


def get_profile_region_size(n_samples):
    """ Get the size of the region of the profile data.

    :param n_samples: number of different samples to record
    :return: the size in bytes used by the profile region
    """
    return PROFILE_HEADER_SIZE_BYTES + (
        n_samples * SIZE_OF_PROFILE_DATA_ENTRY_IN_BYTES)


def reserve_profile_region(spec, region, n_samples):
    """ Reserves the profile region for recording the profile data.

    :param spec: the DSG specification writer
    :param region: region ID for the profile data
    :param n_samples: number of elements being sampled
    :rtype: None
    """
    size = get_profile_region_size(n_samples)
    spec.reserve_memory_region(
        region=region, size=size, label="profilerRegion")


def write_profile_region_data(spec, region, n_samples):
    """ Writes the profile region data.

    :param spec: the DSG specification writer
    :param region: region ID for the profile data
    :param n_samples: number of elements being sampled
    :rtype: None
    """
    spec.switch_write_focus(region)
    spec.write_value(n_samples)


def get_profiling_data(profile_region, tag_labels, txrx, placement):
    """ Utility function to get profile data from a profile region.

    :param profile_region: DSG region to get profiling data out of SDRAM
    :param tag_labels: labels for the profiling data
    :param txrx: SpiNNMan transceiver
    :param placement: placement
    :return: \
        :py:class:`~spinn_front_end_common.interface.profiling.ProfileData`
    """

    profile_data = ProfileData(tag_labels)

    profiling_region_base_address = locate_memory_region_for_placement(
        placement=placement, region=profile_region, transceiver=txrx)

    # Read the profiling data size
    words_written, = _ONE_WORD.unpack_from(txrx.read_memory(
        placement.x, placement.y, profiling_region_base_address, 4))

    # Read the profiling data
    if words_written != 0:
        profile_data.add_data(txrx.read_memory(
            placement.x, placement.y,
            profiling_region_base_address +
            BYTE_OFFSET_OF_PROFILE_DATA_IN_PROFILE_REGION,
            words_written * 4))

    return profile_data
