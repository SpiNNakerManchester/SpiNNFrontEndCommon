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
from pacman.model.graphs.application import ApplicationVertex
from .lpg_splitter import LPGSplitter


class LivePacketGather(ApplicationVertex):
    """
    A vertex that gathers and forwards multicast packets to the host.
    """
    __slots__ = ["__params"]

    def __init__(self, params, label=None):
        """
        :param LivePacketGatherParameters params: The parameters object
        :param str label: An optional label
        """
        super(LivePacketGather, self).__init__(label)
        self.__params = params
        self.splitter = LPGSplitter()

    @property
    def n_atoms(self):
        return 0

    @property
    def params(self):
        return self.__params
