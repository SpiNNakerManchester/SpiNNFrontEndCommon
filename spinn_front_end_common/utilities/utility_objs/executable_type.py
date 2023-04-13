# Copyright (c) 2017 The University of Manchester
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

from enum import Enum
from spinnman.model.enums import CPUState


class ExecutableType(Enum):
    """
    The different types of executable from the perspective of how they
    are started and controlled.
    """

    #: Runs immediately without waiting for barrier and then exits.
    RUNNING = (
        0,
        [CPUState.RUNNING],
        [CPUState.FINISHED],
        False,
        "Runs immediately without waiting for barrier and then exits")
    #: Calls ``spin1_start(SYNC_WAIT)`` and then eventually ``spin1_exit()``.
    SYNC = (
        1,
        [CPUState.SYNC0],
        [CPUState.FINISHED],
        False,
        "Calls spin1_start(SYNC_WAIT) and then eventually spin1_exit()")
    #: Calls ``simulation_run()`` and ``simulation_exit()`` /
    #: ``simulation_handle_pause_resume()``.
    USES_SIMULATION_INTERFACE = (
        2,
        [CPUState.SYNC0, CPUState.SYNC1, CPUState.PAUSED, CPUState.READY],
        [CPUState.READY],
        True,
        "Calls simulation_run() and simulation_exit() / "
        "simulation_handle_pause_resume()")
    #: Situation where there user has supplied no application but for some
    #: reason still wants to run.
    NO_APPLICATION = (
        3,
        [],
        [],
        True,
        "Situation where there user has supplied no application but for "
        "some reason still wants to run")
    #: Runs immediately without waiting for barrier and never ends.
    SYSTEM = (
        4,
        [CPUState.RUNNING],
        [CPUState.RUNNING],
        True,
        "Runs immediately without waiting for barrier and never ends")

    def __new__(cls, value, start_state, end_state,
                supports_auto_pause_and_resume, doc=""):
        # pylint: disable=protected-access, too-many-arguments
        obj = object.__new__(cls)
        obj._value_ = value
        obj.start_state = start_state
        obj.end_state = end_state
        obj.supports_auto_pause_and_resume = supports_auto_pause_and_resume
        obj.__doc__ = doc
        return obj

    def __init__(self, value, start_state, end_state,
                 supports_auto_pause_and_resume, doc=""):
        # pylint: disable=too-many-arguments
        self._value_ = value
        self.__doc__ = doc
        self.start_state = start_state
        self.end_state = end_state
        self.supports_auto_pause_and_resume = supports_auto_pause_and_resume
        self.__doc__ = doc
