import re
import inspect
import struct
import hashlib


# Get lists of appropriate routers, placers and partitioners
def get_valid_components(module, terminator):
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
    data = transceiver.read_memory(x, y, address, length)
    result = struct.unpack_from(data_format, data)[0]
    return result


def get_hash(string):
    """ Create a hash of string as an int

    :param string: The string to create the hash of
    :return: The hash of the string
    :rtype: int
    """
    return int(hashlib.md5(string).hexdigest()[:8], 16)
