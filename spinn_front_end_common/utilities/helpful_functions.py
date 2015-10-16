import re
import inspect
import struct

from spinn_front_end_common.utility_models.live_packet_gather import \
    LivePacketGather
from spinn_front_end_common.utility_models.\
    reverse_ip_tag_multi_cast_source import ReverseIpTagMultiCastSource


def get_valid_components(module, terminator):
    """
    ???????????????
    :param module:
    :param terminator:
    :return:
    """
    terminator = re.compile(terminator + '$')
    return dict(map(lambda (name, router): (terminator.sub('', name),
                                            router),
                inspect.getmembers(module, inspect.isclass)))


def read_data(x, y, address, length, data_format, transceiver):
    """ Reads and converts a single data item from memory
    :param x: chip x
    :param y: chip y
    :param address: base address of the sdram chip to read
    :param length: length to read
    :param data_format: the format to read memory
    :param transceiver: the spinnman interface
    """

    # turn byte array into str for unpack to work
    data = buffer(transceiver.read_memory(x, y, address, length))
    result = struct.unpack_from(data_format, data)[0]
    return result


def auto_detect_database(partitioned_graph):
    """
    autodetects if there is a need to activate the database system
    :param partitioned_graph: the partitioned graph of the application
    problem space.
    :return: a bool which represents if the database is needed
    """
    for vertex in partitioned_graph.subvertices:
        if (isinstance(vertex, LivePacketGather) or
                isinstance(vertex, ReverseIpTagMultiCastSource)):
            return True
    else:
        return False
