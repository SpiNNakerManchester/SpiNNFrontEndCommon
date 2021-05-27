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
import tempfile
from spinn_utilities.log import FormatAdapter
from pacman.executor import injection_decorator
from spinn_front_end_common.interface.simulator_status import (
    RUNNING_STATUS, SHUTDOWN_STATUS)
from spinn_front_end_common.utilities.exceptions import (
    SimulatorRunningException, SimulatorNotSetupException,
    SimulatorShutdownException)

# pylint: disable=global-statement
_simulator = None
__temp_dir = None


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
    global _simulator
    _simulator = new_simulator


def unset_simulator():
    """ Removes the link to the previous simulator and clears injection
    """
    global _simulator, __temp_dir
    _simulator = None
    injection_decorator._instances = list()
    __temp_dir = None


def get_generated_output(output):
    """ Get one of the simulator outputs by name.

    :param str output: The name of the output to retrieve.
    :return: The value (of arbitrary type, dependent on which output),
        or `None` if the variable is not found.
    :raises SimulatorNotSetupException:
        if the system has a status where outputs can't be retrieved
    """
    if _simulator is None:
        raise SimulatorNotSetupException(
            "You need to have ran a simulator before asking for its "
            "generated output.")
    else:
        return _simulator.get_generated_output(output)


def _temp_dir():
    global __temp_dir
    if __temp_dir is None:
        __temp_dir = tempfile.TemporaryDirectory()
    return __temp_dir.name


def provenance_file_path():
    """
    Returns the path to the directory that holds all provenance files

    This will be the path used by the last run call or to be used by
    the next run if it has not yet been called.

    .. note:
        The behaviour when called before setup is subject to change

    :rtpye: str
    :raises SimulatorNotSetupException:
        if the system has a status where path can't be retrieved
    """
    if _simulator is None:
        logger.warning(
            "Invalid simulator so app_provenance_file_path is a tempdir")
        return _temp_dir()
    else:
        # underscore param used avoid exposing a None PyNN parameter
        return _simulator._provenance_file_path


def app_provenance_file_path():
    """
    Returns the path to the directory that holds all app provenance files

    This will be the path used by the last run call or to be used by
    the next run if it has not yet been called.

    .. note:
        The behaviour when called before setup is subject to change

    :rtpye: str
    """
    if _simulator is None:
        logger.warning(
            "Invalid simulator so app_provenance_file_path is a tempdir")
        return _temp_dir()
    else:
        # underscore param used avoid exposing a None PyNN parameter
        return _simulator._app_provenance_file_path


def system_provenance_file_path():
    """
    Returns the path to the directory that holds all provenance files

    This will be the path used by the last run call or to be used by
    the next run if it has not yet been called.

    .. note:
        The behaviour when called before setup is subject to change

    :rtpye: str
    """
    if _simulator is None:
        logger.warning(
            "Invalid simulator so system_provenance_file_path is a tempdir")
        return _temp_dir()
        # underscore param used avoid exposing a None PyNN parameter
        return _simulator._system_provenance_file_path


def report_default_directory():
    """
    Returns the path to the directory that holds all the reports for run

    This will be the path used by the last run call or to be used by
    the next run if it has not yet been called.

    .. note:
        The behaviour when called before setup is subject to change

    :rtpye: str
    """
    if _simulator is None:
        logger.warning(
            "Invalid simulator so report_default_directory is a tempdir")
        return _temp_dir()
    else:
        # underscore param used avoid exposing a None PyNN parameter
        return _simulator._report_default_directory
