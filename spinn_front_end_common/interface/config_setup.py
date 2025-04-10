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
from typing import Set

from spinn_utilities.config_holder import (
    add_default_cfg, clear_cfg_files, get_config_bool)
from spinnman.config_setup import add_spinnman_cfg
from pacman.config_setup import add_pacman_cfg
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.interface_functions \
    import load_using_advanced_monitors

BASE_CONFIG_FILE = "spinnaker.cfg"


def unittest_setup() -> None:
    """
    Does all the steps that may be required before a unit test.

    Resets the configurations so only the local default configurations are
    included.

    Unsets any previous simulators and temporary directories.

    .. note::
        This file should only be called from `spinn_front_end_common/tests`
    """
    clear_cfg_files(True)
    add_spinnaker_cfg()
    FecDataWriter.mock()


def add_spinnaker_cfg() -> None:
    """
    Add the local configuration and all dependent configuration files.
    """
    add_pacman_cfg()  # This add its dependencies too
    add_spinnman_cfg()  # double adds of dependencies ignored
    add_default_cfg(os.path.join(os.path.dirname(__file__), BASE_CONFIG_FILE))


def cfg_paths_skipped() -> Set[str]:
    """
    Set of cfg path that would not be found based on other cfg settings
    """
    skipped = set()
    if not get_config_bool("Reports", "write_energy_report"):
        skipped.add("pathenergyreport")
    if get_config_bool("Machine", "virtual_board"):
        skipped.add("pathdataspeedupreportsrouters")
        skipped.add("pathenergyreport")
        skipped.add("pathmemorymapreport")
    if not get_config_bool("Machine","enable_advanced_monitor_support"):
        skipped.add("pathdataspeedupreportsrouters")
        skipped.add("pathdataspeedupreportsspeeds")
    if get_config_bool("Java", "use_java"):
        skipped.add("pathdataspeedupreportsrouters")
        skipped.add("pathdataspeedupreportsspeeds")
    if not load_using_advanced_monitors():
        skipped.add("pathdataspeedupreportsspeeds")
    return skipped
        #skipped.append("")


