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


class TimerCategory(Enum):
    """
    Different Categories a FecTimer can be in

    """
    # Category Constants
    WAITING = cast('TimerCategory', (auto(), "Waiting"))
    SETTING_UP = cast('TimerCategory', (auto(), "In Setup"))
    RUN_OTHER = cast('TimerCategory', (auto(), "In run other"))
    GET_MACHINE = cast('TimerCategory', (auto(), "Turning on Machine"))
    LOADING = cast('TimerCategory', (auto(), "Loading Stage"))
    DATA_GENERATION = cast('TimerCategory', (auto(), "data_generation"))
    MAPPING = cast('TimerCategory', (auto(), "Mapping Stage"))
    RUN_LOOP = cast('TimerCategory', (auto(), "Running Stage"))
    RESETTING = cast('TimerCategory', (auto(), "Resetting"))
    SHUTTING_DOWN = cast('TimerCategory', (auto(), "Shutting down"))

    def __init__(self, value: 'TimerCategory', category_name: str):
        self._value_ = value
        self._category_name = category_name

    @property
    def category_name(self) -> str:
        return self._category_name
