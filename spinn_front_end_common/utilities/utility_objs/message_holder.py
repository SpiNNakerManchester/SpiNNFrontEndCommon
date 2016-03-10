

class MessageHolder(object):
    """
    MessageHolder: a holder for logger messages from provenance or iobuf
    """

    def __init__(self):
        self._cores_with_messages = dict()
        self._chips_with_messages = dict()
        self._operations_with_messages = dict()

    def add_core_message(self, x, y, p, message, trace=None):
        """
        adds a core message to the pile
        :param x: x coord for message
        :param y: y coord for message
        :param p: p coord for message
        :param message: message
        :param trace: trace to where message came from
        :return: None
        """
        if (x, y, p) not in self._cores_with_messages:
            self._cores_with_messages[(x, y, p)] = list()
        if trace is None:
            trace = ""
        self._cores_with_messages[(x, y, p)].append(
            {'message': message, 'trace': trace})

    def add_operation_message(self, operation_id, message):
        """
        adds a operation message to the pile
        :param operation_id: the id of the operation to add message from
        :param message: the message
        :return: None
        """
        if operation_id not in self._operations_with_messages:
            self._operations_with_messages[operation_id] = list()
        self._operations_with_messages[operation_id].append(message)

    def add_chip_message(self, x, y, message):
        """
        adds a chip message to the pile
        :param x: x coord for message
        :param y: y coord for message
        :param message: message
        :return: None
        """
        if (x, y) not in self._chips_with_messages:
            self._chips_with_messages[(x, y)] = list()
        self._chips_with_messages[(x, y)].append(message)

    def get_core_messages(self, x, y, p):
        """
        returns  a core message from the pile
        :param x: x coord for message
        :param y: y coord for message
        :param p: p coord for message
        :return: a dict with keys 'message' and 'trace'
        """
        if (x, y, p) not in self._cores_with_messages:
            return []
        else:
            return self._cores_with_messages[(x, y, p)]

    def get_cores_with_messages(self):
        """
        returns all cores which have messages
        :return: iterable of tuple of (x, y, p)
        """
        return self._cores_with_messages.keys()

    def get_chip_messages(self, x, y):
        """
        returns a message from a chip
        :param x: x coord for message
        :param y: y coord for message
        :return: iterable of string
        """
        if (x, y) not in self._chips_with_messages:
            return []
        else:
            return self._chips_with_messages[(x, y)]

    def get_chips_with_messages(self):
        """
        returns list of chips with messages
        :return: iterable tuple of (x, y)
        """
        return self._chips_with_messages.keys()

    def get_operation_messages(self, operation_id):
        """
        returns the messages from a operation
        :param operation_id: the operation to look for
        :return: iterable of string
        """
        if operation_id not in self._operations_with_messages:
            return []
        else:
            return self._operations_with_messages[operation_id]

    def get_operations_with_messages(self):
        """
        returns the list of operation ids which have messages
        :return: iterable of string
        """
        return self._operations_with_messages.keys()