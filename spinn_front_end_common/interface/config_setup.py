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

import os
from spinn_utilities.config_holder import (
    add_default_cfg, clear_cfg_files)
from spinnman.config_setup import add_spinnman_cfg
from pacman.config_setup import add_pacman_cfg
from spinn_front_end_common.data.fec_data_writer import FecDataWriter

BASE_CONFIG_FILE = "spinnaker.cfg"


def unittest_setup(*, board_type=None):
    """
    Does all the steps that may be required before a unit test.

    Resets the configurations so only the local default configurations are
    included.

    Unsets any previous simulators and temporary directories.

    .. note::
        This file should only be called from `spinn_front_end_common/tests`

    :param board_type: Value to say how to confuire the system.
        This includes defining what a VirtualMachine would be
        Can be 1 for Spin1 boards, 2 for Spin2 boards or
        None if the test do not depend on knowing the board type.
    :type board_type: None or int
    """
    clear_cfg_files(True)
    FecDataWriter.mock()
    add_spinnaker_cfg(board_type)


def add_spinnaker_cfg(board_type):
    """
    Add the local configuration and all dependent configuration files.

    :param board_type: Value to say how to confuire the system.
        This includes defining what a VirtualMachine would be
        Can be 1 for Spin1 boards, 2 for Spin2 boards or
        None if the test do not depend on knowing the board type.
    :type board_type: None or int
    """
    add_default_cfg(os.path.join(os.path.dirname(__file__), BASE_CONFIG_FILE))
    add_pacman_cfg(board_type)  # This add its dependencies too
    add_spinnman_cfg(board_type)  # double adds of dependencies ignored
