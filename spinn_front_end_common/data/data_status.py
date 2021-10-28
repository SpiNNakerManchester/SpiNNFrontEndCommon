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
from spinn_front_end_common.utilities.exceptions import (
    SimulatorDataNotMocked, SimulatorNotSetupException,
    SimulatorDataNotYetAvialable, SimulatorShutdownException)


class Data_Status(Enum):
    """ Different states the Data can be in.
    """
    NOT_SETUP = (
        0, SimulatorNotSetupException)
    MOCKED = (
        1, SimulatorDataNotMocked)
    SETUP = (
        2, SimulatorDataNotYetAvialable)

    def __new__(cls, value, exception):
        # pylint: disable=protected-access
        obj = object.__new__(cls)
        obj._value_ = value
        obj.exception = exception
        return obj
