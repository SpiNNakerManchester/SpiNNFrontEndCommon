# Copyright (c) 2019 The University of Manchester
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
from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class BitFieldSummary:
    """
    Summary description of generated bitfields.
    """

    total_merged: Union[int, str]
    max_per_chip: Union[int, str]
    lowest_per_chip: Union[int, str]
    total_to_merge: int
    max_to_merge_per_chip: Union[int, str]
    low_to_merge_per_chip: Union[int, str]
    average_per_chip_merged: Union[float, str]
    average_per_chip_to_merge: float
