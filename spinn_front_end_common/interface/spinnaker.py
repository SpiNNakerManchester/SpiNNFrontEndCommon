# Copyright (c) 2016 The University of Manchester
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

from typing import Type

from spinn_utilities.overrides import overrides

from spinn_front_end_common.interface.config_setup import (
    add_spinnaker_cfg, add_spinnaker_template)
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.abstract_spinnaker_base import (
    AbstractSpinnakerBase)


class SpiNNaker(AbstractSpinnakerBase):
    """
    The implementation of the SpiNNaker simulation interface.

    .. note::
        You can instantiate this directly from application code.
        It is the callers responsibility to only have a single instance.
    """

    @overrides(AbstractSpinnakerBase._add_cfg_defaults_and_template)
    def _add_cfg_defaults_and_template(self) -> None:
        add_spinnaker_cfg()
        add_spinnaker_template()

    @property
    @overrides(AbstractSpinnakerBase._user_cfg_file)
    def _user_cfg_file(self) -> str:
        # Any name can be used here.
        return "spinnaker.cfg"

    @property
    @overrides(AbstractSpinnakerBase._data_writer_cls)
    def _data_writer_cls(self) -> Type[FecDataWriter]:
        return FecDataWriter
