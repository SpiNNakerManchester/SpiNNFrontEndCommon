from spinn_front_end_common.utilities import exceptions


class MultiCastCommand(object):
    """ A command to be sent to a vertex
    """

    def __init__(
            self, key, payload=None, time=None, repeat=0,
            delay_between_repeats=0):
        """

        :param key: The key of the command
        :type key: int
        :param payload: The payload of the command
        :type payload: int
        :param time: The time within the simulation at which to send the\
                    command, or None if this is not a timed command
        :type time: int
        :param repeat: The number of times that the command should be\
                    repeated after sending it once.  This could be used to\
                    ensure that the command is sent despite lost packets.\
                    Must be between 0 and 65535
        :type repeat: int
        :param delay_between_repeats: The amount of time in micro seconds to\
                    wait between sending repeats of the same command.\
                    Must be between 0 and 65535, and must be 0 if repeat is 0
        :type delay_between_repeats: int
        :raise SpynnakerException: If the repeat or delay are out of range
        """

        if repeat < 0 or repeat > 0xFFFF:
            raise exceptions.ConfigurationException(
                "repeat must be between 0 and 65535")
        if delay_between_repeats < 0 or delay_between_repeats > 0xFFFF:
            raise exceptions.ConfigurationException(
                "delay_between_repeats must be between 0 and 65535")
        if delay_between_repeats > 0 and repeat == 0:
            raise exceptions.ConfigurationException(
                "If repeat is 0, delay_betweeen_repeats must be 0")

        self._time = time
        self._key = key

        self._payload = payload
        self._repeat = repeat
        self._delay_between_repeats = delay_between_repeats

    @property
    def time(self):
        return self._time

    @property
    def is_timed(self):
        return self._time is not None

    @property
    def key(self):
        return self._key

    @property
    def repeat(self):
        return self._repeat

    @property
    def delay_between_repeats(self):
        return self._delay_between_repeats

    @property
    def payload(self):
        """ Get the payload of the command.

        :return: The payload of the command, or None if there is no payload
        :rtype: int
        """
        return self._payload

    @payload.setter
    def payload(self, payload):
        self._payload = payload

    @property
    def is_payload(self):
        """ Determine if this command has a payload.  By default, this returns\
            True if the payload passed in to the constructor is not None, but\
            this can be overridden to indicate that a payload will be\
            generated, despite None being passed to the constructor

        :return: True if there is a payload, False otherwise
        :rtype: bool
        """
        return self._payload is not None

    def __repr__(self):
        return \
            "MultiCastCommand(time={}, key={}, payload={},"\
            " time_between_repeat={}, repeats={})".format(
                self._time, self._key, self._payload,
                self._delay_between_repeats, self._repeat)
