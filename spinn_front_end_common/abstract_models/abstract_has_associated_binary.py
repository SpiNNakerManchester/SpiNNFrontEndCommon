from six import add_metaclass

from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractHasAssociatedBinary(object):

    @abstractmethod
    def get_binary_file_name(self):
        """ Get the binary name to be run for vertices of this vertex
        """

    __slots__ = ()
