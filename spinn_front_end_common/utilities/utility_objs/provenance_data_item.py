
class ProvenanceDataItem(object):
    """ Container for provenance data
    """

    def __init__(self, names, value, report=False, message=None):
        """

        :param names: A list of strings representing the hierarchy of naming\
                    of this item
        :param value: The value of the item
        :param report: True if the item should be reported to the user
        :param message: The message to send to the end user if report is True
        """
        self._names = names
        self._value = value
        self._report = report
        self._message = message

    @property
    def message(self):
        """ The message to report to the end user, or None if no message
        """
        return self._message

    @property
    def report(self):
        """ True if this provenance data entry needs reporting to the end user
        """
        return self._report

    @property
    def names(self):
        """ The hierarchy of names of this bit of provenance data
        """
        return self._names

    @property
    def value(self):
        """ The value of the item
        """
        return self._value

    def __repr__(self):
        return "{}:{}:{}:{}".format(
            self._names, self._value, self._report, self._message)

    def __str__(self):
        if self._report:
            return self._message
        return "{}: {}".format(self._names, self._value)
