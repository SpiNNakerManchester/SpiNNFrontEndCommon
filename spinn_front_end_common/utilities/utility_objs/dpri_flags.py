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


class DPRIFlags(Enum):
    """
    SCP Dropped Packet Reinjection (DPRI) packet type flags.
    """
    MULTICAST = 1
    POINT_TO_POINT = 2
    NEAREST_NEIGHBOUR = 4
    FIXED_ROUTE = 8

    def __new__(cls, value, doc=""):
        # pylint: disable=protected-access
        obj = object.__new__(cls)
        obj._value_ = value
        obj.__doc__ = doc
        return obj

    def __init__(self, value, doc=""):
        self._value_ = value
        self.__doc__ = doc
