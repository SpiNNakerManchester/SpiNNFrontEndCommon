from data_specification import utility_calls

import logging
import struct
from spinn_front_end_common.interface.profiling.profile_data import ProfileData

logger = logging.getLogger(__name__)


def get_profiling_data(
        self, profile_region, tag_labels, machine_time_step, run_time_ms,
        txrx, placements, graph_mapper):
    """ Utility function to get profile data from a profile region
    """

    profile_data = ProfileData(tag_labels, machine_time_step, run_time_ms)
    subvertices = graph_mapper.get_subvertices_from_vertex(self)
    for subvertex in subvertices:
        placement = placements.get_placement_of_subvertex(subvertex)
        (x, y, p) = placement.x, placement.y, placement.p
        subvertex_slice = graph_mapper.get_subvertex_slice(subvertex)
        lo_atom = subvertex_slice.lo_atom
        logger.debug(
            "Reading profile from chip {}, {}, core {}, "
            "lo_atom {}".format(x, y, p, lo_atom))

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
