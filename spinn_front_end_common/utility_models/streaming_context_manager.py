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


class StreamingContextManager(object):
    """
    The implementation of the context manager object for streaming
    configuration control.
    """
    __slots__ = ["_gatherers"]

    def __init__(self, gatherers):
        """
        :param iterable(DataSpeedUpPacketGatherMachineVertex) gatherers:
        """
        self._gatherers = list(gatherers)

    def __enter__(self):
        for gatherer in self._gatherers:
            gatherer.load_system_routing_tables()
        for gatherer in self._gatherers:
            gatherer.set_cores_for_data_streaming()

    def __exit__(self, _type, _value, _tb):
        for gatherer in self._gatherers:
            gatherer.unset_cores_for_data_streaming()
        for gatherer in self._gatherers:
            gatherer.load_application_routing_tables()
        return False
