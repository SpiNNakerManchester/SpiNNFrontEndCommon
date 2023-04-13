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


class ReinjectorSCPCommands(Enum):
    """
    SCP Command codes for reinjection
    """
    SET_ROUTER_WAIT1_TIMEOUT = 0
    SET_ROUTER_WAIT2_TIMEOUT = 1
    SET_PACKET_TYPES = 2
    GET_STATUS = 3
    RESET_COUNTERS = 4
    EXIT = 5
    CLEAR = 6

    def __new__(cls, value, doc=""):
        # pylint: disable=protected-access, unused-argument
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, value, doc=""):
        self._value_ = value
        self.__doc__ = doc
