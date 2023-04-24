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

from spinnman.model.enums import ExecutableType as _ExecutableType


class ExecutableType(object):
    """
    This class is deprecated. Please use spinnman.model.enums.ExecutableType
    """
    RUNNING = _ExecutableType.RUNNING

    SYNC = _ExecutableType.SYNC

    USES_SIMULATION_INTERFACE = _ExecutableType.USES_SIMULATION_INTERFACE

    NO_APPLICATION = _ExecutableType.NO_APPLICATION

    SYSTEM = _ExecutableType.SYSTEM
