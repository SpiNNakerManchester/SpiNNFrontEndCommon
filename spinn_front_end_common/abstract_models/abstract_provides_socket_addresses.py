from six import add_metaclass
from abc import abstractmethod
from abc import ABCMeta


@add_metaclass(ABCMeta)
class AbstractProvidesSocketAddresses(object):
    """ Allows a vertex to provide a collection of socket addresses for the
    notification protocol.
    """

    @abstractmethod
    def get_socket_addresses(self):
        """ Get the socket addresses from this vertex
        :return: A list of socket addresses
        """
        pass
