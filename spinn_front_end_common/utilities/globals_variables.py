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

# pylint: disable=global-statement
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

    :param SimulatorInterface new_simulator: The simulator to set.
    """
    global _simulator, _failed_state, _cached_simulator
    if _failed_state is None:
        raise ValueError("Unexpected call to set_simulator before "
                         "set_failed_state")
    _simulator = new_simulator
    _cached_simulator = None


def unset_simulator(to_cache_simulator=None):
    """ Destroy the current simulator.

    :param SimulatorInterface to_cache_simulator:
        a cached version for allowing data extraction
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

    :param FailedState new_failed_state: the failure marker
    """
    # pylint: disable=unidiomatic-typecheck
    global _failed_state
    if _failed_state is None:
        _failed_state = new_failed_state
    elif type(new_failed_state) != type(_failed_state):
        raise ValueError("You may only setup/init one type of simulator")


def _last_simulator():
    """ Get last simulator to be used.

    Before setup this will return None.
    Between setup and end this will return the simulator.
    After end this will return the previous simulator
    """
    global _simulator, _cached_simulator
    if _simulator is not None:
        return _simulator
    if _cached_simulator is not None:
        return _cached_simulator
    if _failed_state is not None:
        return None
    else:
        raise ValueError(
            "There should be some sort of simulator set. Why am i here?!")


def get_generated_output(output):
    """ Get one of the simulator outputs by name.

    :param str output: The name of the output to retrieve.
    :return: The value (of arbitrary type, dependent on which output),
        or `None` if the variable is not found.
    :raises ValueError:
        if the system is in a state where outputs can't be retrieved
    """
    simulator = _last_simulator()
    if simulator is None:
        raise ValueError(
            "You need to have ran a simulator before asking for its "
            "generated output.")
    else:
        return simulator.get_generated_output(output)


def provenance_file_path():
    """
    Returns the path to the directory that holds all provenance files

    This will be the path used by the last run call or to be used by
    the next run if it has not yet been called.

    :rtpye: str
    :raises ValueError:
        if the system is in a state where path can't be retrieved
    """
    simulator = _last_simulator()
    if simulator is None:
        raise ValueError(
            "You need to have setup a simulator before asking for its "
            "provenance_file_path.")
    else:
        # underscore param used avoid exposing a None PyNN parameter
        return simulator._provenance_file_path


def app_provenance_file_path():
    """
    Returns the path to the directory that holds all app provenance files

    This will be the path used by the last run call or to be used by
    the next run if it has not yet been called.

    :rtpye: str
    :raises ValueError:
        if the system is in a state where path can't be retrieved
    """
    simulator = _last_simulator()
    if simulator is None:
        raise ValueError(
            "You need to have setup a simulator before asking for its "
            "app_provenance_file_path.")
    else:
        # underscore param used avoid exposing a None PyNN parameter
        return simulator._app_provenance_file_path


def system_provenance_file_path():
    """
    Returns the path to the directory that holds all provenance files

    This will be the path used by the last run call or to be used by
    the next run if it has not yet been called.

    :rtpye: str
    :raises ValueError:
        if the system is in a state where path can't be retrieved
    """
    simulator = _last_simulator()
    if simulator is None:
        raise ValueError(
            "You need to have setup a simulator before asking for its "
            "system_provenance_file_path.")
    else:
        # underscore param used avoid exposing a None PyNN parameter
        return simulator._system_provenance_file_path


def run_report_directory():
    """
    Returns the path to the directory that holds all the reports for run

    This will be the path used by the last run call or to be used by
    the next run if it has not yet been called.

    :rtpye: str
    :raises ValueError:
        if the system is in a state where path can't be retrieved
    """
    simulator = _last_simulator()
    if simulator is None:
        raise ValueError(
            "You need to have setup a simulator before asking for its "
            "run_report_directory.")
    else:
        # underscore param used avoid exposing a None PyNN parameter
        return simulator._report_default_directory


def config():
    """ Provides access to the configuration used or a best effort to the
    config to be used

    If called before setup will return the values found in the config file
    BEFORE any cleanup alterations that setup could do.

    After setup will return the simulation config even if end has been called

    :rtype: ~spinn_front_end_common.interface.config_handler.ConfigHandler
    """
    global _failed_state
    simulator = _last_simulator()
    if simulator is None:
        return _failed_state.config
    else:
        return simulator.config
