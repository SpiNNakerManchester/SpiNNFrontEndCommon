import re
import inspect
import struct


# Get lists of appropriate routers, placers and partitioners
def get_valid_components(module, terminator):
    terminator = re.compile(terminator + '$')
    return dict(map(lambda (name, router): (terminator.sub('', name),
                                            router),
                inspect.getmembers(module, inspect.isclass)))


def read_and_convert(x, y, address, length, data_format, transceiver):
    """ Reads and converts a single data item from memory
    """

    # turn byte array into str for unpack to work
    data = transceiver.read_memory(x, y, address, length)
    result = struct.unpack_from(data_format, data)
    return result
