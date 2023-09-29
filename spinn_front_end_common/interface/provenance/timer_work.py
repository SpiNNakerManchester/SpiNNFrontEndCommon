# Copyright (c) 2022 The University of Manchester
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

from enum import auto, Enum


class TimerWork(Enum):
    """
    Different Work types an Algorithm could be doing
    """

    OTHER = (auto(), "Other")
    GET_MACHINE = (auto(), "Turning on Machine")
    LOADING = (auto(), "Loading Stage")
    # LOADING
    BITFIELD = (auto(), "BitField work")
    # Only for on Machine Compression
    COMPRESSING = (auto(), "Compressing")
    CONTROL = (auto(), "Control")
    SYNAPSE = (auto(), "Expanding Synapse")
    RUNNING = (auto(), "Running")
    EXTRACTING = (auto(), "Extracting")
    # TODO is in right to treat this separately
    EXTRACT_DATA = (auto(), "Extracting")
    REPORT = (auto(), "Reporting")

    def __new__(cls, value, work_name):
        # pylint: disable=protected-access
        obj = object.__new__(cls)
        obj._value_ = value
        obj._work_name = work_name
        return obj

    @property
    def work_name(self):
        return self._work_name
