
class SocketAddress(object):
    """ Data holder for a socket interface for notification protocol.
    """

    def __init__(self, notify_host_name, notify_port_no, listen_port):
        self._notify_host_name = notify_host_name
        self._notify_port_no = notify_port_no
        self._listen_port = listen_port

    @property
    def notify_host_name(self):
        """ The notify host name
        """
        return self._notify_host_name

    @property
    def notify_port_no(self):
        """ The notify port no
        """
        return self._notify_port_no

    @property
    def listen_port(self):
        """ The port to listen to for responses
        """
        return self._listen_port

    def __eq__(self, other):
        if isinstance(other, SocketAddress):
            if self.__hash__() == other.__hash__():
                return True
            else:
                return False
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return (hash(self._listen_port) + hash(self._notify_host_name) +
                hash(self._notify_port_no))
