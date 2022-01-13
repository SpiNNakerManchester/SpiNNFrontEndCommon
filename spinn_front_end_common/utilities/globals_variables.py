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

import logging
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.interface.simulator_status import (
    RUNNING_STATUS, SHUTDOWN_STATUS)
from spinn_front_end_common.utilities.exceptions import (
    SimulatorRunningException, SimulatorNotSetupException,
    SimulatorShutdownException)

# pylint: disable=global-statement
_simulator = None
__temp_dir = None
__unittest_mode = False


logger = FormatAdapter(logging.getLogger(__name__))

logger = FormatAdapter(logging.getLogger(__name__))


def check_simulator():
    """ Check if a simulator has been setup but not yet shut down

    :raises: SimulatorNotSetupException, SimulatorShutdownException
    """
    if _simulator is None:
        raise SimulatorNotSetupException(
            "This call is only valid after setup has been called")
    if _simulator._status in SHUTDOWN_STATUS:
        raise SimulatorShutdownException(
            "This call is only valid between setup and end/stop")


def has_simulator():
    """ Check if a simulator has been setup but not yet shut down

    Should behave in the same way as check_simulator except that it returns
    False where check_simulator raises and exception and True when it does not

    :rtype: bool
    """
    if _simulator is None:
        return False
    if _simulator._status in SHUTDOWN_STATUS:
        return False
    return True


def get_simulator():
    """ Get the current simulator object.

    :rtype: ~spinn_front_end_common.interface.AbstractSpinnakerBase
    :raises: SimulatorNotSetupException, SimulatorShutdownException
    """
    check_simulator()
    return _simulator


def get_last_simulator():
    """ Get the last simulator object setup.

    Unlike get_simulator this method will also return a simulator that has
        been shutdown.

    :rtype: ~spinn_front_end_common.interface.AbstractSpinnakerBase
    :raises: SimulatorNotSetupException
    """
    if _simulator is None:
        raise SimulatorNotSetupException(
            "This call is only valid after setup has been called")
    return _simulator


def get_not_running_simulator():
    """ Get the current simulator object and verify that it is not running.

    :rtype: ~spinn_front_end_common.interface.AbstractSpinnakerBase
    :raises: SimulatorNotSetupException, SimulatorShutdownException,
        SimulatorRunningException
    """
    check_simulator()
    if _simulator._status in RUNNING_STATUS:
        raise SimulatorRunningException(
            "Illegal call while a simulation is already running")
    return _simulator


def set_simulator(new_simulator):
    """ Set the current simulator object.

    :param new_simulator: The simulator to set.
    :type new_simulator:
        ~spinn_front_end_common.interface.AbstractSpinnakerBase
    """
    global _simulator, __temp_dir, __unittest_mode
    _simulator = new_simulator
    __unittest_mode = False
    __temp_dir = None


def setup_for_unittest():
    """ Removes the link to the previous simulator and clears injection

    This will also delete any temp_dir from previous tests.

    As this call is not required before calling set_simulator
    so should only be called by unittest_setup.

    """
    global _simulator, __temp_dir, __unittest_mode
    _simulator = None
    __unittest_mode = True
    __temp_dir = None
