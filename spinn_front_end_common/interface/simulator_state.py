# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from enum import Enum


class Simulator_State(Enum):
    """ Different states the Simulator could be in.
    """
    #: init called
    INIT = (0, "init called")
    #: inside run method
    IN_RUN = (1, "inside run method")
    #: finished run method, but running forever
    RUN_FOREVER = (2, "finish run method but running forever")
    #: run ended shutdown not called
    FINISHED = (3, "run ended shutdown not called")
    #: shutdown called
    SHUTDOWN = (4, "shutdown called")
    #: stop requested in middle of run forever
    STOP_REQUESTED = (5, "stop requested in middle of run forever")

    def __new__(cls, value, doc=""):
        # pylint: disable=protected-access
        obj = object.__new__(cls)
        obj._value_ = value
        obj.__doc__ = doc
        return obj

    def __init__(self, value, doc=""):
        self._value_ = value
        self.__doc__ = doc
