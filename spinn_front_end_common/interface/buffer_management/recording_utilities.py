import struct
from spinn_front_end_common.interface.buffer_management.storage_objects\
    import ChannelBufferState
from spinn_front_end_common.utilities.constants import (
    SARK_PER_MALLOC_SDRAM_USAGE, SDP_PORTS)

# The offset of the last sequence number field in bytes
_LAST_SEQUENCE_NUMBER_OFFSET = 4 * 6

# The offset of the memory addresses in bytes
_FIRST_REGION_ADDRESS_OFFSET = 4 * 7

# the number of data elements inside the recording region before
# recording regions sizes are stored.
_RECORDING_ELEMENTS_BEFORE_REGION_SIZES = 7

# The Buffer traffic type
TRAFFIC_IDENTIFIER = "BufferTraffic"

_ONE_WORD = struct.Struct("<I")
_TWO_SHORTS = struct.Struct("<HH")


def get_recording_header_size(n_recorded_regions):
    """ Get the size of the data to be written for the recording header

    :param n_recorded_regions: The number of regions to be recorded
    """

    # See recording.h/recording_initialise for data included in the header
    return (_RECORDING_ELEMENTS_BEFORE_REGION_SIZES +
            (2 * n_recorded_regions)) * 4


def get_recording_data_constant_size(n_recorded_regions):
    """ Get the size of the recorded data to be reserved that doesn't

    :param n_recorded_regions: The number of regions to be recorded
    :rtype: int
    """
    return (

        # The storage of the recording state
        (n_recorded_regions *
         ChannelBufferState.size_of_channel_state()) +

        # The SARK allocation of SDRAM overhead
        (n_recorded_regions * SARK_PER_MALLOC_SDRAM_USAGE))


def get_recording_header_array(
        recorded_region_sizes,
        time_between_triggers=0, buffer_size_before_request=None, ip_tags=None,
        buffering_tag=None):
    """ Get data to be written for the recording header

    :param recorded_region_sizes:\
        A list of sizes of each region to be recorded.\
        A size of 0 is acceptable.
    :param time_between_triggers:\
        The minimum time between requesting reads of any region
    :param buffer_size_before_request:\
        The amount of buffer to fill before a read request is sent
    :param ip_tags: A list of IP tags to extract the buffer tag from
    :param buffering_tag: The tag to use for buffering requests
    :return: An array of values to be written as the header
    :rtype: list(int)
    """

    # Find the tag if required
    buffering_output_tag = 0
    buffering_output_dest_x = 0
    buffering_output_dest_y = 0
    if buffering_tag is not None:
        buffering_output_tag = buffering_tag
    elif ip_tags:
        buffering_output_tag = None
        for tag in ip_tags:
            if tag.traffic_identifier == TRAFFIC_IDENTIFIER:
                buffering_output_tag = tag.tag
                buffering_output_dest_x = tag.destination_x
                buffering_output_dest_y = tag.destination_y
                break
        else:
            raise Exception("Buffering tag not found")

    # See recording.h/recording_initialise for data included in the header
    data = list()

    # The parameters
    data.append(len(recorded_region_sizes))
    data.append(buffering_output_tag)
    data.append(_ONE_WORD.unpack(_TWO_SHORTS.pack(
        buffering_output_dest_y, buffering_output_dest_x))[0])
    data.append(SDP_PORTS.OUTPUT_BUFFERING_SDP_PORT.value)
    if buffer_size_before_request is not None:
        data.append(buffer_size_before_request)
    else:

        # If no buffer size before request, assume not buffering, so ensure
        # that the buffering will not be activated
        data.append(max(recorded_region_sizes) + 256)
    data.append(time_between_triggers)

    # The last sequence number (to be filled in by C code)
    data.append(0)

    # The pointers for each region (to be filled in by C code)
    data.extend([0 for _ in recorded_region_sizes])

    # The size of the regions
    data.extend(recorded_region_sizes)

    return data


def get_last_sequence_number(placement, transceiver, recording_data_address):
    """ Read the last sequence number from the data

    :param placement: The placement from which to read the sequence number
    :param transceiver: The transceiver to use to read the sequence number
    :param recording_data_address:\
        The address of the recording data from which to read the number
    :rtype: int
    """
    data = transceiver.read_memory(
        placement.x, placement.y,
        recording_data_address + _LAST_SEQUENCE_NUMBER_OFFSET, 4)
    return _ONE_WORD.unpack_from(data)[0]


def get_region_pointer(placement, transceiver, recording_data_address, region):
    """ Get a pointer to a recording region

    :param placement: The placement from which to read the pointer
    :param transceiver: The transceiver to use to read the pointer
    :param recording_data_address:\
        The address of the recording data from which to read the pointer
    :param region: The index of the region to get the pointer of
    :rtype: int
    """
    data = transceiver.read_memory(
        placement.x, placement.y,
        recording_data_address + _FIRST_REGION_ADDRESS_OFFSET + (region * 4),
        4)
    return _ONE_WORD.unpack_from(data)[0]
