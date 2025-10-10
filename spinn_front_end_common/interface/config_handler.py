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

from configparser import NoOptionError
import logging
import os
import shutil
import traceback
from typing import cast, List, Optional, Type

from spinn_utilities.log import FormatAdapter
from spinn_utilities.configs.camel_case_config_parser import FALSES
from spinn_utilities.config_holder import (
    config_options, has_config_option, load_config, get_config_bool,
    get_config_int, get_config_str, get_config_str_list, get_timestamp_path,
    set_config)
from spinnman.spinnman_simulation import SpiNNManSimulation
from spinn_front_end_common.interface.interface_functions.\
    insert_chip_power_monitors_to_graphs import sample_chip_power_monitor
from spinn_front_end_common.interface.interface_functions.\
    insert_extra_monitor_vertices_to_graphs import (
        sample_monitor_vertex, sample_speedup_vertex)
from spinn_front_end_common.interface.provenance import LogStoreDB
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.utilities.exceptions import ConfigurationException

logger = FormatAdapter(logging.getLogger(__name__))

# options names are all lower without _ inside config
_DEBUG_ENABLE_OPTS = frozenset([
    "cleariobufduringrun", "extractiobuf"])
_DEBUG_MAPPING_OPTS = frozenset([
    "routertablecompressasfaraspossible", "runcompressionchecker"])


class ConfigHandler(SpiNNManSimulation):
    """
    Superclass of AbstractSpinnakerBase that handles function only
    dependent of the configuration and the order its methods are called.
    """

    __slots__ = ()

    def __init__(self, data_writer_cls: Optional[Type[FecDataWriter]] = None):
        """
        :param data_writer_cls:
            Class of the DataWriter used to store the global data
        """
        load_config()
        if data_writer_cls is None:
            data_writer_cls = FecDataWriter
        super().__init__(data_writer_cls)

        logger.set_log_store(LogStoreDB())

        # set up machine targeted data
        self._debug_configs()
        self._previous_handler()
        self._reserve_system_vertices()
        self._ensure_provenance_for_energy_report()

    @property
    def _data_writer(self) -> FecDataWriter:
        return cast(FecDataWriter, self._untyped_data_writer)

    def __toggle_config(self, section: str, option: str, to_false: List[str],
                        to_true: List[str]) -> None:
        previous = get_config_str(section, option).lower()
        if previous in to_true:
            set_config(section, option, "True")
            logger.info(f"[{section}]:{option} now True instead of {previous}")
        elif previous in to_false:
            set_config(section, option, "False")

    def _debug_configs(self) -> None:
        """
        Adjusts and checks the configuration based on mode and
        `reports_enabled`.

        :raises ConfigurationException:
        """
        mode = get_config_str("Mode", "mode").lower()

        if mode == "production":
            to_false = ["info", "debug"]
            to_true = []
            logger.info("As mode is Production running all reports and "
                        "keeping files is turned off "
                        "unless specifically asked for in cfg")
        elif mode == "info":
            logger.info(
                "As mode is Info the following cfg setting have been changed")
            to_false = ["debug"]
            to_true = ["info"]
        elif mode == "debug":
            logger.info("As mode is Debug the following cfg setting "
                        "have been changed")
            to_false = []
            to_true = ["info", "debug"]
        elif mode == "all":
            logger.info(
                "As mode is All the following cfg setting have been changed")
            to_false = []
            to_true = ["info", "debug"]
            to_true.extend(FALSES)
        else:
            raise ConfigurationException(f"Unexpected {mode=}")

        for option in config_options("Reports"):
            # options names are all lower without _ inside config
            if (option in _DEBUG_ENABLE_OPTS or
                    option[:4] in ["keep", "read", "writ"]):
                self.__toggle_config("Reports", option, to_false, to_true)
        for option in config_options("Mapping"):
            # options names are all lower without _ inside config
            if option in _DEBUG_MAPPING_OPTS or option[:8] == "validate":
                self.__toggle_config("Mapping", option, to_false, to_true)

    def _previous_handler(self) -> None:
        self._error_on_previous("loading_algorithms")
        self._error_on_previous("application_to_machine_graph_algorithms")
        self._error_on_previous("machine_graph_to_machine_algorithms")
        self._error_on_previous("machine_graph_to_virtual_machine_algorithms")
        self._replaced_cfg("Reports",
                           "write_routing_table_reports", "write_uncompressed")
        self._replaced_cfg("Reports",
                           "write_routing_tables_from_machine_reports",
                           "write_compressed, write_compression_comparison,"
                           " and write_compression_summary")
        self._replaced_cfg("Reports",
                           "write_routing_compression_checker_report",
                           "run_compression_checker")
        self._replaced_cfg("Reports", "report_enabled",
                           "[Mode]mode = Production to turn off most reports")

    def _error_on_previous(self, option: str) -> None:
        try:
            get_config_str_list("Mapping", option)
        except NoOptionError:
            # GOOD!
            return
        raise ConfigurationException(
            f"cfg setting {option} is no longer supported! "
            "See https://spinnakermanchester.github.io/common_pages/"
            "Algorithms.html.")

    def _replaced_cfg(self, section: str, previous: str, new: str) -> None:
        if has_config_option(section, previous):
            if get_config_bool(section, previous):
                raise ConfigurationException(
                    f"cfg setting [{section}] {previous} "
                    f"is no longer supported! Use {new} instead")
            else:
                logger.warning(f"cfg setting [{section}] {previous} "
                               f"is no longer supported! Use {new} instead")

    def _reserve_system_vertices(self) -> None:
        """
        Reserves the sizes for the system vertices
        """
        if get_config_bool("Reports", "write_energy_report"):
            self._data_writer.add_sample_monitor_vertex(
                sample_chip_power_monitor(), True)
        if (get_config_bool("Machine", "enable_advanced_monitor_support")
                or get_config_bool("Machine", "enable_reinjection")):
            self._data_writer.add_sample_monitor_vertex(
                sample_monitor_vertex(), True)
            self._data_writer.add_sample_monitor_vertex(
                sample_speedup_vertex(), False)

    def _remove_excess_folders(
            self, max_kept: int, starting_directory: str,
            remove_errored_folders: Optional[bool]) -> None:
        try:
            files_in_report_folder = os.listdir(starting_directory)

            # while there's more than the valid max, remove the oldest one
            if len(files_in_report_folder) > max_kept:
                # sort files into time frame
                files_in_report_folder.sort(
                    key=lambda temp_file: os.path.getmtime(
                        os.path.join(starting_directory, temp_file)))

                # remove only the number of files required, and only if they
                # have the finished flag file created
                num_files_to_remove = len(files_in_report_folder) - max_kept
                files_removed = 0
                files_not_closed = 0
                for current_oldest_file in files_in_report_folder:
                    finished_flag = os.path.join(os.path.join(
                        starting_directory, current_oldest_file),
                        self._data_writer.FINISHED_FILENAME)
                    errored_flag = os.path.join(os.path.join(
                        starting_directory, current_oldest_file),
                        self._data_writer.ERRORED_FILENAME)
                    finished_flag_exists = os.path.exists(finished_flag)
                    errored_flag_exists = os.path.exists(errored_flag)
                    if finished_flag_exists or (
                            errored_flag_exists and remove_errored_folders):
                        shutil.rmtree(os.path.join(
                            starting_directory, current_oldest_file),
                            ignore_errors=True)
                        files_removed += 1
                    else:
                        files_not_closed += 1
                    if files_removed + files_not_closed >= num_files_to_remove:
                        break
                if files_not_closed > max_kept // 4:
                    logger.warning(
                        "{} has {} old reports that have not been closed",
                        starting_directory, files_not_closed)
        except IOError:
            # This might happen if there is an open file, or more than one
            # process in the same folder, but we shouldn't die because of it
            pass

    def _set_up_report_specifics(self) -> None:
        # clear and clean out folders considered not useful any more
        report_dir_path = self._data_writer.get_report_dir_path()
        if os.listdir(report_dir_path):
            self._remove_excess_folders(
                get_config_int("Reports", "max_reports_kept"),
                report_dir_path,
                get_config_bool("Reports", "remove_errored_folders"))

        # store timestamp in latest/time_stamp for provenance reasons
        time_of_run_file_name = get_timestamp_path(
            "tpath_stack_trace")
        with open(time_of_run_file_name, "w", encoding="utf-8") as f:
            f.write("Traceback of setup call:\n")
            traceback.print_stack(file=f)

    def _ensure_provenance_for_energy_report(self) -> None:
        if get_config_bool("Reports", "write_energy_report"):
            set_config("Reports", "read_router_provenance_data", "True")
            set_config("Reports", "read_placements_provenance_data", "True")
