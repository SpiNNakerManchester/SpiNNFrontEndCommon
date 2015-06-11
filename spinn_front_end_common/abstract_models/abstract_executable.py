"""
"""
from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractExecutable(object):
    """ An object that can be executed on SpiNNaker
    """

    @abstractmethod
    def get_binary_file_name(self):
        """ Get the name of the binary file to be executed.  Can be a full\
            path to the file, or just the file name; if the latter, a known\
            set of paths will be searched for the binary
        :rtype: str
        """
