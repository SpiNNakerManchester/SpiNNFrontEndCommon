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

# pylint: disable=global-statement, protected-access
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


def machine_time_step():
    """ The machine timestep, in microseconds

    ..note: In unittest mode this returns the default 1000

    :rtype: int
    :raises SimulatorNotSetupException:
        If the simulator has not been setup
    """
    if _simulator is None:
        #  set by unittest_setup
        if __unittest_mode:
            return 1000
        else:
            raise SimulatorNotSetupException(
                "machine_time_step() not supported before sim.setup.")
    else:
        if _simulator._status in SHUTDOWN_STATUS:
            logger.warning(
                "simulator shutdown before machine_time_step requested")
    return _simulator.machine_time_step


def machine_time_step_ms():
    """ The machine timestep, in microseconds

    Semantic sugar for machine_time_step() / 1000.

    ..note: In unittest mode this returns the default 1.0

    :rtype: float
    :raises SimulatorNotSetupException:
        If the simulator has not been setup
    """
    if _simulator is None:
        #  set by unittest_setup
        if __unittest_mode:
            return 1.0
        else:
            raise SimulatorNotSetupException(
                "machine_time_step_ms() not supported before sim.setup.")
    else:
        if _simulator._status in SHUTDOWN_STATUS:
            logger.warning(
                "simulator shutdown before machine_time_step_ms requested")
    return _simulator.machine_time_step_ms


def machine_time_step_per_ms():
    """ The machine timesteps in a microseconds

    Semantic sugar for 1000 / machine_time_step()

    ..note: In unittest mode this returns the default 1.0

    :rtype: float
    :raises SimulatorNotSetupException:
        If the simulator has not been setup
    """
    if _simulator is None:
        #  set by unittest_setup
        if __unittest_mode:
            return 1.0
        else:
            raise SimulatorNotSetupException(
                "machine_time_step_per_ms() not supported before sim.setup.")
    else:
        if _simulator._status in SHUTDOWN_STATUS:
            logger.warning(
                "simulator shutdown before machine_time_step_per_ms requested")
    return _simulator.machine_time_step_per_ms


def time_scale_factor():
    """ The time scaling factor.

    ..note: In unittest mode this returns the default 1

    :rtype: int
    :raises ValueError:
        if the system is in a state where machine_timestep can't be retrieved
    :raises SimulatorNotSetupException:
        If the simulator has not been setup
    """
    if _simulator is None:
        #  set by unittest_setup
        if __unittest_mode:
            return 1
        else:
            raise SimulatorNotSetupException(
                "time_scale_factor() not supported before sim.setup.")
    else:
        if _simulator._status in SHUTDOWN_STATUS:
            logger.warning(
                "simulator shutdown before time_scale_factorrequested")
    return _simulator.time_scale_factor


def provenance_file_path():
    """
    Returns the path to the directory that holds all provenance files

    This will be the path used by the last run call or to be used by
    the next run if it has not yet been called.

    ..note: In unittest mode this returns a tempdir shared by all path methods

    :rtpye: str
    :raises SimulatorNotSetupException:
        If the simulator has not been setup
    """
    if _simulator is None:
        if __unittest_mode:
            return _temp_dir()
        else:
            raise SimulatorNotSetupException(
                "provenance_file_path() not supported before sim.setup.")
    else:
        # underscore param used avoid exposing a None PyNN parameter
        return _simulator._provenance_file_path


def app_provenance_file_path():
    """
    Returns the path to the directory that holds all app provenance files

    This will be the path used by the last run call or to be used by
    the next run if it has not yet been called.

    ..note: In unittest mode this returns a tempdir shared by all path methods

    :rtpye: str
    :raises SimulatorNotSetupException:
        If the simulator has not been setup
    """
    if _simulator is None:
        if __unittest_mode:
            return _temp_dir()
        else:
            raise SimulatorNotSetupException(
                "app_provenance_file_path() not supported before sim.setup.")
    else:
        # underscore param used avoid exposing a None PyNN parameter
        return _simulator._app_provenance_file_path


def system_provenance_file_path():
    """
    Returns the path to the directory that holds all provenance files

    This will be the path used by the last run call or to be used by
    the next run if it has not yet been called.

    ..note: In unittest mode this returns a tempdir shared by all path methods

    :rtpye: str
    :raises SimulatorNotSetupException:
        If the simulator has not been setup
    """
    if _simulator is None:
        if __unittest_mode:
            return _temp_dir()
        else:
            raise SimulatorNotSetupException(
                "system_provenance_file_path not supported before sim.setup.")
    else:
        # underscore param used avoid exposing a None PyNN parameter
        return _simulator._system_provenance_file_path


def report_default_directory():
    """
    Returns the path to the directory that holds all the reports for run

    This will be the path used by the last run call or to be used by
    the next run if it has not yet been called.

    ..note: In unittest mode this returns a tempdir shared by all path methods

    :rtpye: str
    :raises SimulatorNotSetupException:
        If the simulator has not been setup
    """
    if _simulator is None:
        if __unittest_mode:
            return _temp_dir()
        else:
            raise SimulatorNotSetupException(
                "report_default_directory() not supported before sim.setup.")
    else:
        # underscore param used avoid exposing a None PyNN parameter
        return _simulator._report_default_directory


def where_is_chip(chip):
    if _simulator is None:
        raise SimulatorNotSetupException(
            "You need to have ran a simulator before asking for its "
            "generated output.")
    else:
        return _simulator.machine.where_is_chip(chip)


def where_is_xy(x, y):
    if _simulator is None:
        raise SimulatorNotSetupException(
            "You need to have ran a simulator before asking for its "
            "generated output.")
    else:
        return _simulator.machine.where_is_xy(x, y)
