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
    add_default_cfg, add_template, clear_cfg_files, get_config_bool)
from spinn_utilities.configs.camel_case_config_parser import optionxform

from spinnman.config_setup import add_spinnman_cfg, man_cfg_paths_skipped

from pacman.config_setup import add_pacman_cfg, packman_cfg_paths_skipped
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.interface_functions \
    import load_using_advanced_monitors

BASE_CONFIG_FILE = "spinnaker.cfg"
TEMPLATE_FILE = "spinnaker.cfg.template"


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
    add_template(os.path.join(os.path.dirname(__file__), TEMPLATE_FILE))


def fec_cfg_paths_skipped() -> Set[str]:
    """
    Set of cfg path that may not be found based on other cfg settings

    Assuming mode = Debug

    :returns: list of cfg path options that point to paths that may not exist
    """
    skipped = man_cfg_paths_skipped()
    skipped.update(packman_cfg_paths_skipped())
    if not get_config_bool("Reports", "write_energy_report"):
        skipped.add(optionxform("path_energy_report"))

    if get_config_bool("Machine", "virtual_board"):
        skipped.add(optionxform("path_data_speed_up_reports_routers"))
        skipped.add(optionxform("path_drift_report"))
        skipped.add(optionxform("path_energy_report"))
        skipped.add(optionxform("path_fixed_routes_report"))
        skipped.add(optionxform("path_iobuf_app"))
        skipped.add(optionxform("path_iobuf_system"))
        skipped.add(optionxform("path_java_log"))
        skipped.add(optionxform("path_json_java_placements"))
        skipped.add(optionxform("path_memory_map_report_map"))
        skipped.add(optionxform("path_memory_map_reports"))
        skipped.add(optionxform("path_tag_allocation_reports_machine"))

    if not get_config_bool("Machine", "enable_advanced_monitor_support"):
        skipped.add(optionxform("path_data_speed_up_reports_routers"))
        skipped.add(optionxform("path_fixed_routes_report"))
        skipped.add(optionxform("path_data_speed_up_reports_speeds"))

    if get_config_bool("Java", "use_java"):
        skipped.add(optionxform("path_data_speed_up_reports_routers"))
        skipped.add(optionxform("path_data_speed_up_reports_speeds"))
    else:
        skipped.add(optionxform("path_java_log"))
        skipped.add(optionxform("path_json_java_placements"))

    if not load_using_advanced_monitors():
        skipped.add(optionxform("path_data_speed_up_reports_speeds"))
    return skipped
