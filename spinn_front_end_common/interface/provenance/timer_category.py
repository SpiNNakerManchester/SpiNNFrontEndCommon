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


class TimerCategory(Enum):
    """
    Different Categories a FecTimer can be in

    """
    # Category Constants
    WAITING = (auto(), "Waiting")
    SETTING_UP = (auto(), "In Setup")
    RUN_OTHER = (auto(), "In run other")
    GET_MACHINE = (auto(), "Turning on Machine")
    LOADING = (auto(), "Loading Stage")
    MAPPING = (auto(), "Mapping Stage")
    RUN_LOOP = (auto(), "Running Stage")
    RESETTING = (auto(), "Resetting")
    SHUTTING_DOWN = (auto(), "Shutting down")

    def __new__(cls, value: int, __: str) -> 'TimerCategory':
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, value: int, category_name: str) -> None:
        """
        :param value: Enum ID
        :param category_name: Name to use when describing this category
        """
        _ = value
        self._category_name = category_name

    @property
    def category_name(self) -> str:
        """
        The category name as passed into the init.
        """
        return self._category_name
