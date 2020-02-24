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
_cached_simulator = None


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
    global _simulator, _failed_state, _cached_simulator
    if _failed_state is None:
        raise ValueError("Unexpected call to set_simulator before "
                         "set_failed_state")
    _simulator = new_simulator
    _cached_simulator = None


def unset_simulator(to_cache_simulator=None):
    """ Destroy the current simulator.

    :param to_cache_simulator: \
        a cached version for allowing data extraction
    :type to_cache_simulator: SimulatorInterface
    """
    global _simulator, _cached_simulator
    _simulator = None
    _cached_simulator = to_cache_simulator

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


def get_generated_output(output):
    global _simulator, _failed_state, _cached_simulator
    if _simulator is not None:
        return _simulator.get_generated_output(output)
    elif _failed_state is not None:
        if _cached_simulator is not None:
            return _cached_simulator.get_generated_output(output)
        else:
            raise ValueError(
                "You need to have ran a simulator before asking for its "
                "generated output, and the simulator needs to be cached "
                "before you can request outputs.")
    else:
        raise ValueError(
            "There should be some sort of simulator set. Why am i here?!")
