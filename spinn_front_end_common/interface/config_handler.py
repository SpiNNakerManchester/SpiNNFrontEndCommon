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
from typing import Optional, Type
from spinn_utilities.log import FormatAdapter
from spinn_utilities.config_holder import (
    config_options, has_config_option, load_config, get_config_bool,
    get_config_int, get_config_str, get_config_str_list, set_config)
from spinn_front_end_common.interface.interface_functions.\
    insert_chip_power_monitors_to_graphs import sample_chip_power_monitor
from spinn_front_end_common.interface.interface_functions.\
    insert_extra_monitor_vertices_to_graphs import (
        sample_monitor_vertex, sample_speedup_vertex)
from spinn_front_end_common.interface.provenance import LogStoreDB
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.utilities.exceptions import ConfigurationException

logger = FormatAdapter(logging.getLogger(__name__))

APP_DIRNAME = 'application_generated_data_files'
TIMESTAMP_FILENAME = "time_stamp"
WARNING_LOGS_FILENAME = "warning_logs.txt"

# options names are all lower without _ inside config
_DEBUG_ENABLE_OPTS = frozenset([
    "reportsenabled",
    "cleariobufduringrun", "extractiobuf"])
_DEBUG_MAPPING_OPTS = frozenset([
    "routertablecompressasfaraspossible", "runcompressionchecker"])
_REPORT_DISABLE_OPTS = frozenset([
    "cleariobufduringrun", "extractiobuf"])


class ConfigHandler(object):
    """
    Superclass of AbstractSpinnakerBase that handles function only
    dependent of the configuration and the order its methods are called.
    """

    __slots__ = (
        # The writer and therefore view of the global data
        "_data_writer", )

    def __init__(self, data_writer_cls: Optional[Type[FecDataWriter]] = None):
        """
        :param FecDataWriter data_writer:
            The Global data writer object
        """
        load_config()

        if data_writer_cls:
            self._data_writer = data_writer_cls.setup()
        else:
            self._data_writer = FecDataWriter.setup()
        logger.set_log_store(LogStoreDB())

        # set up machine targeted data
        self._debug_configs()
        self._previous_handler()
        self._reserve_system_vertices()

    def _debug_configs(self) -> None:
        """
        Adjusts and checks the configuration based on mode and
        `reports_enabled`.

        :raises ConfigurationException:
        """
        if get_config_str("Mode", "mode") == "Debug":
            for option in config_options("Reports"):
                # options names are all lower without _ inside config
                if option in _DEBUG_ENABLE_OPTS or option[:5] == "write":
                    if not get_config_bool("Reports", option):
                        set_config("Reports", option, "True")
                        logger.info("As mode == \"Debug\", [Reports] {} "
                                    "has been set to True", option)
            for option in config_options("Mapping"):
                # options names are all lower without _ inside config
                if option in _DEBUG_MAPPING_OPTS:
                    if not get_config_bool("Mapping", option):
                        set_config("Mapping", option, "True")
                        logger.info("As mode == \"Debug\", [Mapping] {} "
                                    "has been set to True", option)
        elif not get_config_bool("Reports", "reportsEnabled"):
            for option in config_options("Reports"):
                # options names are all lower without _ inside config
                if option in _REPORT_DISABLE_OPTS or option[:5] == "write":
                    if not get_config_bool("Reports", option):
                        set_config("Reports", option, "False")
                        logger.info(
                            "As reportsEnabled == \"False\", [Reports] {} "
                            "has been set to False", option)

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

    def _error_on_previous(self, option) -> None:
        try:
            get_config_str_list("Mapping", option)
        except NoOptionError:
            # GOOD!
            return
        raise ConfigurationException(
            f"cfg setting {option} is no longer supported! "
            "See https://spinnakermanchester.github.io/common_pages/"
            "Algorithms.html.")

    def _replaced_cfg(self, section: str, previous: str, new: str):
        if has_config_option(section, previous):
            if get_config_bool(section, previous):
                raise ConfigurationException(
                    f"cfg setting [{section}] {previous} "
                    f"is no longer supported! Use {new} instead")
            else:
                logger.warning(f"cfg setting [{section}] {previous} "
                               f"is no longer supported! Use {new} instead")

    def _reserve_system_vertices(self):
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

    def _adjust_config(self, runtime: Optional[float]):
        """
        Adjust and checks the configuration based on runtime

        :param runtime:
        :type runtime: int or bool
        :raises ConfigurationException:
        """
        if runtime is None:
            if get_config_bool("Reports", "write_energy_report"):
                set_config("Reports", "write_energy_report", "False")
                logger.info("[Reports]write_energy_report has been set to "
                            "False as runtime is set to forever")

    def _remove_excess_folders(
            self, max_kept: int, starting_directory: str,
            remove_errored_folders: Optional[bool]):
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
                    if finished_flag_exists and (
                            not errored_flag_exists or remove_errored_folders):
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
        timestamp_dir_path = self._data_writer.get_timestamp_dir_path()
        time_of_run_file_name = os.path.join(
            timestamp_dir_path, TIMESTAMP_FILENAME)
        _, timestamp = os.path.split(timestamp_dir_path)
        with open(time_of_run_file_name, "w", encoding="utf-8") as f:
            f.writelines(timestamp)
            f.write("\n")
            f.write("Traceback of setup call:\n")
            traceback.print_stack(file=f)

    def __write_marker_file(self, file_name: str):
        app_file_name = os.path.join(
            self._data_writer.get_timestamp_dir_path(), file_name)
        with open(app_file_name, "w", encoding="utf-8") as f:
            # TODO What should this file contain?
            f.writelines("file_name")

    def write_finished_file(self) -> None:
        """
        Write a finished file that allows file removal to only remove
        folders that are finished.
        """
        self.__write_marker_file(FINISHED_FILENAME)

    def write_errored_file(self) -> None:
        """
        Writes an ``errored`` file that allows file removal to only remove
        folders that have errors if requested to do so
        """
        self.__write_marker_file(ERRORED_FILENAME)
