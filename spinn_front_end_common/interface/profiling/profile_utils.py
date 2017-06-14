from data_specification import utility_calls

import logging
import struct
from spinn_front_end_common.interface.profiling.profile_data import ProfileData

logger = logging.getLogger(__name__)


def get_profile_header_size():
    """ Get the size of the header of the profiler
    """
    return 4


def get_profile_region_size(n_samples):
    """ Get the size of the region of the profile data
    """
    return (4 + (n_samples * 8))


def reserve_profile_region(spec, region, n_samples):
    """ Reserves the profile region for recording the profile data
    """
    if n_samples != 0:
        size = get_profile_region_size(n_samples)
        spec.reserve_memory_region(
            region=region, size=size, label="profilerRegion", empty=True)


def write_profile_region_data(spec, region, n_samples):
    """ Writes the profile region data
    """
    spec.switch_write_focus(region)
    spec.write_value(n_samples)


def get_profiling_data(
        self, profile_region, tag_labels, txrx, placement):
    """ Utility function to get profile data from a profile region
    """

    profile_data = ProfileData(tag_labels)
    (x, y, p) = placement.x, placement.y, placement.p

    # Get the App Data for the core
    app_data_base_address = \
        txrx.get_cpu_information_from_core(x, y, p).user[0]

    # Get the position of the value buffer
    profiling_region_base_address_offset = \
        utility_calls.get_region_base_address_offset(
            app_data_base_address,
            self._profile_region)
    profiling_region_base_address_buf = buffer(txrx.read_memory(
        x, y, profiling_region_base_address_offset, 4))
    profiling_region_base_address = \
        struct.unpack_from("<I", profiling_region_base_address_buf)[0]

    # Read the profiling data size
    words_written_data =\
        buffer(txrx.read_memory(
            x, y, profiling_region_base_address + 4, 4))
    words_written = \
        struct.unpack_from("<I", words_written_data)[0]

    # Read the profiling data
    profiling_data = txrx.read_memory(
        x, y, profiling_region_base_address + 8, words_written * 4)
    profile_data.add_data(profiling_data)

    return profile_data
