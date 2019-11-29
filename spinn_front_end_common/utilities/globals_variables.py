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

from pacman.executor import injection_decorator

_failed_state = None
_simulator = None


def get_simulator():
    """ Get the current simulator object.

    :rtype: SimulatorInterface
    """
    global _simulator, _failed_state
    if _simulator is None:
        if _failed_state is None:
            raise ValueError("You must import one of the simulator classes "
                             "before calling get_simulator")
        return _failed_state
    return _simulator


def get_not_running_simulator():
    """ Get the current simulator object and verify that it is not running.

    :rtype: SimulatorInterface
    """
    global _simulator, _failed_state
    if _simulator is None:
        if _failed_state is None:
            raise ValueError("You must import one of the simulator classes "
                             "before calling get_simulator")
        return _failed_state
    _simulator.verify_not_running()
    return _simulator


def set_simulator(new_simulator):
    """ Set the current simulator object.

    :param new_simulator: The simulator to set.
    :type new_simulator: SimulatorInterface
    """
    global _simulator, _failed_state
    if _failed_state is None:
        raise ValueError("Unexpected call to set_simulator before "
                         "set_failed_state")
    _simulator = new_simulator


def unset_simulator():
    """ Destroy the current simulator.
    """
    global _simulator
    _simulator = None
    injection_decorator._instances = list()


def has_simulator():
    """ Check if a simulator is operational.

    :rtype: bool
    """
    global _simulator
    return _simulator is not None


def set_failed_state(new_failed_state):
    """ Install a marker to say that the simulator has failed.

    :param new_failed_state: the failure marker
    :type new_failed_state: FailedState
    """
    # pylint: disable=unidiomatic-typecheck
    global _failed_state
    if _failed_state is None:
        _failed_state = new_failed_state
    elif type(new_failed_state) != type(_failed_state):
        raise ValueError("You may only setup/init one type of simulator")

def us_to_timesteps(simtime_in_us):
    """
    Converts the simtime in us to timesteps assuming the caller is using the\
    machine default timestep

    simtime_in_us MUST be a multiple of the default machine timestep

    :raises ConfigurationException: If called except between start and end
    :raises ValueError: An Exception is raised if no simulator is active or\
    if the simtime is not a multiple of that simulators machine timestep
    the machine default timestep
    :param simtime_in_us: time in us to convert to default timestep
    :return: number of timesteps
    """
    timestep = get_simulator().machine_time_step
    timesteps = simtime_in_us // timestep
    check = timesteps * timestep
    if check != simtime_in_us:
        raise ValueError(
            "{} is not a multiple of the default machine timestep {}".format(
                simtime_in_us, timestep))
    return timesteps
