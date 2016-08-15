from six import add_metaclass
from abc import ABCMeta


@add_metaclass(ABCMeta)
class AbstractWritesRawMemory(object):
    """ An object that writes raw memory to be loaded on to the machine
    """

    def write_raw_memory(self, memory_file, placement):
        """ Write the memory that needs to be read by this vertex

        :param memory_file: A file-like object to which data is to be written
        :param placement: the placement to which this file object is assocted
        :type memory_file:\
            :py:class:`spinn_storage_handlers.abstract_classes.abstract_data_writer.AbstractDataWriter`
        """
