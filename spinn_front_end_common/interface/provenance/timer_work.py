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
from typing import cast


class TimerWork(Enum):
    """
    Different Work types an Algorithm could be doing
    """

    OTHER = cast('TimerWork', (auto(), "Other"))
    GET_MACHINE = cast('TimerWork', (auto(), "Turning on Machine"))
    LOADING = cast('TimerWork', (auto(), "Loading Stage"))
    # LOADING
    BITFIELD = cast('TimerWork', (auto(), "BitField work"))
    # Only for on Machine Compression
    COMPRESSING = cast('TimerWork', (auto(), "Compressing"))
    CONTROL = cast('TimerWork', (auto(), "Control"))
    SYNAPSE = cast('TimerWork', (auto(), "Expanding Synapse"))
    RUNNING = cast('TimerWork', (auto(), "Running"))
    EXTRACTING = cast('TimerWork', (auto(), "Extracting"))
    # TODO is in right to treat this separately
    EXTRACT_DATA = cast('TimerWork', (auto(), "Extracting"))
    REPORT = cast('TimerWork', (auto(), "Reporting"))

    def __init__(self, value: 'TimerWork', work_name: str):
        self._value_ = value
        self._work_name = work_name

    @property
    def work_name(self) -> str:
        return self._work_name
