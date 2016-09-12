from abc import ABCMeta
from six import add_metaclass
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractHasAssociatedBinary(object):

    @abstractmethod
    def get_binary_file_name(self):
        """ Get the binary name to be run for vertices of this vertex
        """
