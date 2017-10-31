from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractUsesMemoryIO(object):
    """ Indicates that the class will write data using the MemoryIO interface
    """

    @abstractmethod
    def get_memory_io_data_size(self):
        """ Get the size of the data area to allocate to this vertex

        :return: The size of the data area in bytes
        :rtype: int
        """

    @abstractmethod
    def write_data_to_memory_io(self, memory, tag):
        """ Write the data to the given memory object

        :param memory: The memory to write to
        :type memory: :py:class:`~spinnman.utilities.io.memory_io.MemoryIO`
        :param tag: The tag given to the allocated memory
        :type tag: int
        """
