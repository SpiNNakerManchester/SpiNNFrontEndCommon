from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractHasAssociatedBinary(object):
    """ Marks a machine graph vertex that can be launched on a SpiNNaker core.
    """

    __slots__ = ()

    @abstractmethod
    def get_binary_file_name(self):
        """ Get the binary name to be run for this vertex.

        :rtype: str
        """

    @abstractmethod
    def get_binary_start_type(self):
        """ Get the start type of the binary to be run.

        :rtype:\
            :py:class:`~spinn_front_end_common.utilities.utility_objs.ExecutableType`
        """
