# Copyright (c) 2016 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import Optional
from spinn_front_end_common.utilities.exceptions import ConfigurationException


class MultiCastCommand(object):
    """
    A command to be sent to a vertex.
    """

    def __init__(
            self, key: int, payload: Optional[int] = None, *,
            time: Optional[int] = None, repeat: int = 0,
            delay_between_repeats: int = 0):
        """
        :param key: The key of the command
        :param payload: The payload of the command
        :param time: The time within the simulation at which to send the
            command, or ``None`` if this is not a timed command
        :param repeat:
            The number of times that the command should be repeated after
            sending it once. This could be used to ensure that the command is
            sent despite lost packets. Must be between 0 and 65535
        :param delay_between_repeats:
            The amount of time in microseconds to wait between sending repeats
            of the same command. Must be between 0 and 65535, and must be 0 if
            repeat is 0
        :raise ConfigurationException: If the repeat or delay are out of range
        """
        if repeat < 0 or repeat > 0xFFFF:
            raise ConfigurationException(
                "repeat must be between 0 and 65535")
        if delay_between_repeats < 0 or delay_between_repeats > 0xFFFF:
            raise ConfigurationException(
                "delay_between_repeats must be between 0 and 65535")
        if delay_between_repeats > 0 and repeat == 0:
            raise ConfigurationException(
                "If repeat is 0, delay_betweeen_repeats must be 0")

        self._time = time
        self._key = key

        self._payload = payload
        self._repeat = repeat
        self._delay_between_repeats = delay_between_repeats

    @property
    def time(self) -> Optional[int]:
        """
        The time within the simulation at which to send the
        command, or `None` if this is not a timed command.
        """
        return self._time

    @property
    def is_timed(self) -> bool:
        """
        Whether this command is a timed command.
        """
        return self._time is not None

    @property
    def key(self) -> int:
        """
        The key of the command
        """
        return self._key

    @property
    def repeat(self) -> int:
        """
        The number of times that the command should be repeated
        """
        return self._repeat

    @property
    def delay_between_repeats(self) -> int:
        """
        The amount of time in microseconds to wait between sending repeats
        """
        return self._delay_between_repeats

    @property
    def payload(self) -> Optional[int]:
        """
        The payload of the command, or `None` if there is no payload.
        """
        return self._payload

    @property
    def is_payload(self) -> bool:
        """
        Whether this command has a payload. By default, this returns
        True if the payload passed in to the constructor is not `None`, but
        this can be overridden to indicate that a payload will be
        generated, despite `None` being passed to the constructor
        """
        return self.payload is not None

    def __repr__(self) -> str:
        return (
            f"MultiCastCommand(time={self._time}, key={self._key}, "
            f"payload={self.payload}, "
            f"time_between_repeat={self._delay_between_repeats}, "
            f"repeats={self._repeat})")
