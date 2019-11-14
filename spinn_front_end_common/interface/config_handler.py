# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import logging
import os
import errno
import shutil
import time
import spinn_utilities.conf_loader as conf_loader
from spinn_utilities.log import FormatAdapter
from spinn_machine import Machine
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.helpful_functions import (
    read_config, read_config_boolean, read_config_int)

logger = FormatAdapter(logging.getLogger(__name__))

APP_DIRNAME = 'application_generated_data_files'
CONFIG_FILE = "spinnaker.cfg"
FINISHED_FILENAME = "finished"
REPORTS_DIRNAME = "reports"
TIMESTAMP_FILENAME = "time_stamp"


class ConfigHandler(object):
    """
    Subclass of AbstractSpinnaker base that handles function only dependent
    of the config and the order its methods are called
    """

    __slots__ = [
        #
        "_app_data_runtime_folder",

        #
        "_app_data_top_simulation_folder",

        # the interface to the cfg files. supports get get_int etc
        "_config",

        #
        "_json_folder",

        #
        "_provenance_file_path",

        #
        "_app_provenance_file_path",

        #
        "_system_provenance_file_path",

        #
        "_report_default_directory",

        #
        "_report_simulation_top_directory",

        #
        "_this_run_time_string",

        #
        "_use_virtual_board",

        # If not None, path to append pacman executor provenance info to
        "_pacman_executor_provenance_path",
    ]

    def __init__(self, configfile, default_config_paths, validation_cfg):
        # global params
        if default_config_paths is None:
            default_config_paths = []
        default_config_paths.insert(0, os.path.join(
            os.path.dirname(__file__), CONFIG_FILE))

        self._config = conf_loader.load_config(
            filename=configfile, defaults=default_config_paths,
            validation_cfg=validation_cfg)

        # set up machine targeted data
        self._use_virtual_board = self._config.getboolean(
            "Machine", "virtual_board")

        # Pass max_machine_cores to Machine so if effects everything!
        max_machine_core = self._read_config_int("Machine", "max_machine_core")
        if max_machine_core is not None:
            Machine.set_max_cores_per_chip(max_machine_core)

        self._app_data_runtime_folder = None
        self._app_data_top_simulation_folder = None
        self._json_folder = None
        self._provenance_file_path = None
        self._report_default_directory = None
        self._report_simulation_top_directory = None
        self._this_run_time_string = None

    def _adjust_config(self, runtime, debug_enable_opts, report_disable_opts):
        """ Adjust and checks config based on runtime and mode

        :param runtime:
        :type runtime: int or bool
        :type debug_enable_opts: frozenset(str)
        :type report_disable_opts: frozenset(str)
        :raises ConfigurationException
        """
        if self._config.get("Mode", "mode") == "Debug":
            for option in self._config.options("Reports"):
                # options names are all lower without _ inside config
                if option in debug_enable_opts or option[:5] == "write":
                    try:
                        if not self._config.get_bool("Reports", option):
                            self._config.set("Reports", option, "True")
                            logger.info("As mode == \"Debug\", [Reports] {} "
                                        "has been set to True", option)
                    except ValueError:
                        pass
        elif not self._config.getboolean("Reports", "reportsEnabled"):
            for option in self._config.options("Reports"):
                # options names are all lower without _ inside config
                if option in report_disable_opts or option[:5] == "write":
                    try:
                        if not self._config.get_bool("Reports", option):
                            self._config.set("Reports", option, "False")
                            logger.info(
                                "As reportsEnabled == \"False\", [Reports] {} "
                                "has been set to False", option)
                    except ValueError:
                        pass

        if runtime is None:
            if self._config.getboolean(
                    "Reports", "write_energy_report") is True:
                self._config.set("Reports", "write_energy_report", "False")
                logger.info("[Reports]write_energy_report has been set to "
                            "False as runtime is set to forever")
            if self._config.get_bool(
                    "EnergySavings", "turn_off_board_after_discovery") is True:
                self._config.set(
                    "EnergySavings", "turn_off_board_after_discovery", "False")
                logger.info("[EnergySavings]turn_off_board_after_discovery has"
                            " been set to False as runtime is set to forever")

        if self._use_virtual_board:
            if self._config.getboolean(
                    "Reports", "write_energy_report") is True:
                self._config.set("Reports", "write_energy_report", "False")
                logger.info("[Reports]write_energy_report has been set to "
                            "False as using virtual boards")
            if self._config.get_bool(
                    "EnergySavings", "turn_off_board_after_discovery") is True:
                self._config.set(
                    "EnergySavings", "turn_off_board_after_discovery", "False")
                logger.info("[EnergySavings]turn_off_board_after_discovery has"
                            " been set to False as s using virtual boards")
            if self._config.getboolean(
                    "Reports", "write_board_chip_report") is True:
                self._config.set("Reports", "write_board_chip_report", "False")
                logger.info("[Reports]write_board_chip_report has been set to"
                            " False as using virtual boards")

    def child_folder(self, parent, child_name, must_create=False):
        """
        :param must_create: If `True`, the directory named by `child_name`\
            (but not necessarily its parents) must be created by this call,\
            and an exception will be thrown if this fails.
        :raises OSError: if the directory existed ahead of time and creation\
            was required by the user
        """
        child = os.path.join(parent, child_name)
        if must_create:
            # Throws OSError or FileExistsError (a subclass of OSError) if the
            # directory exists.
            os.makedirs(child)
        elif not os.path.exists(child):
            self._make_dirs(child)
        return child

    def _remove_excess_folders(self, max_kept, starting_directory):
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
                        FINISHED_FILENAME)
                    if os.path.exists(finished_flag):
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

    def _set_up_report_specifics(self, n_calls_to_run):
        """
        :param n_calls_to_run: \
            the counter of how many times run has been called.
        :type n_calls_to_run: int
        :return: The folder for this run, the time_stamp
        """

        default_report_file_path = self._config.get_str(
            "Reports", "default_report_file_path")
        # determine common report folder
        if default_report_file_path == "DEFAULT":
            directory = os.getcwd()

            # global reports folder
            report_default_directory = self.child_folder(
                directory, REPORTS_DIRNAME)
        elif default_report_file_path == "REPORTS":
            report_default_directory = REPORTS_DIRNAME
            if not os.path.exists(report_default_directory):
                self._make_dirs(report_default_directory)
        else:
            report_default_directory = self.child_folder(
                default_report_file_path, REPORTS_DIRNAME)

        # clear and clean out folders considered not useful anymore
        if os.listdir(report_default_directory):
            self._remove_excess_folders(
                self._config.getint("Reports", "max_reports_kept"),
                report_default_directory)

        # determine the time slot for later while also making the report folder
        if self._this_run_time_string is None:
            while True:
                try:
                    timestamp = self.__make_timestamp()
                    self._report_simulation_top_directory = self.child_folder(
                        report_default_directory, timestamp, must_create=True)
                    self._this_run_time_string = timestamp
                    break
                except OSError:
                    time.sleep(0.5)
        else:
            self._report_simulation_top_directory = self.child_folder(
                report_default_directory, self._this_run_time_string)

        # create sub folder within reports for sub runs
        # (where changes need to be recorded)
        self._report_default_directory = self.child_folder(
            self._report_simulation_top_directory, "run_{}".format(
                n_calls_to_run))

        # store timestamp in latest/time_stamp for provenance reasons
        time_of_run_file_name = os.path.join(
            self._report_simulation_top_directory, TIMESTAMP_FILENAME)
        with open(time_of_run_file_name, "w") as f:
            f.writelines(self._this_run_time_string)

    @staticmethod
    def __make_timestamp():
        now = datetime.datetime.now()
        return "{:04}-{:02}-{:02}-{:02}-{:02}-{:02}-{:02}".format(
            now.year, now.month, now.day,
            now.hour, now.minute, now.second, now.microsecond)

    def set_up_output_application_data_specifics(self, n_calls_to_run):
        """
        :param n_calls_to_run: \
            the counter of how many times run has been called.
        :type n_calls_to_run: int
        :return: the run folder for this simulation to hold app data
        """
        where_to_write_application_data_files = self._config.get(
            "Reports", "default_application_data_file_path")
        if where_to_write_application_data_files == "DEFAULT":
            where_to_write_application_data_files = os.getcwd()

        application_generated_data_file_folder = self.child_folder(
            where_to_write_application_data_files, APP_DIRNAME)
        # add time stamped folder for this run
        self._app_data_top_simulation_folder = self.child_folder(
            application_generated_data_file_folder, self._this_run_time_string)

        # remove folders that are old and above the limit
        self._remove_excess_folders(
            self._config.getint("Reports", "max_application_binaries_kept"),
            application_generated_data_file_folder)

        # store timestamp in latest/time_stamp
        time_of_run_file_name = os.path.join(
            self._app_data_top_simulation_folder, TIMESTAMP_FILENAME)
        with open(time_of_run_file_name, "w") as f:
            f.writelines(str(self._this_run_time_string))

        # create sub folder within reports for sub runs
        # (where changes need to be recorded)
        self._app_data_runtime_folder = self.child_folder(
            self._app_data_top_simulation_folder, "run_{}".format(
                n_calls_to_run))

    def _set_up_output_folders(self, n_calls_to_run):
        """ Sets up all outgoing folders by creating\
            a new timestamp folder for each and clearing

        :rtype: None
        """

        # set up reports default folder
        self._set_up_report_specifics(n_calls_to_run)

        # set up application report folder
        self.set_up_output_application_data_specifics(n_calls_to_run)

        if self._read_config_boolean("Reports",
                                     "writePacmanExecutorProvenance"):
            self._pacman_executor_provenance_path = os.path.join(
                self._report_default_directory,
                "pacman_executor_provenance.rpt")

        self._json_folder = os.path.join(
            self._report_default_directory, "json_files")
        if not os.path.exists(self._json_folder):
            self._make_dirs(self._json_folder)

        # make a folder for the provenance data storage
        self._provenance_file_path = os.path.join(
            self._report_default_directory, "provenance_data")
        if not os.path.exists(self._provenance_file_path):
            self._make_dirs(self._provenance_file_path)

        # make application folder for provenance data storage
        self._app_provenance_file_path = os.path.join(
            self._provenance_file_path, "app_provenance_data")
        if not os.path.exists(self._app_provenance_file_path):
            self._make_dirs(self._app_provenance_file_path)

        # make system folder for provenance data storage
        self._system_provenance_file_path = os.path.join(
            self._provenance_file_path, "system_provenance_data")
        if not os.path.exists(self._system_provenance_file_path):
            self._make_dirs(self._system_provenance_file_path)

    def write_finished_file(self):
        """ Write a finished file that allows file removal to only remove \
            folders that are finished.
        """
        app_file_name = os.path.join(self._app_data_top_simulation_folder,
                                     FINISHED_FILENAME)
        with open(app_file_name, "w") as f:
            f.writelines("finished")

        app_file_name = os.path.join(self._report_simulation_top_directory,
                                     FINISHED_FILENAME)
        with open(app_file_name, "w") as f:
            f.writelines("finished")

    def _read_config(self, section, item):
        return read_config(self._config, section, item)

    def _read_config_int(self, section, item):
        return read_config_int(self._config, section, item)

    def _read_config_boolean(self, section, item):
        return read_config_boolean(self._config, section, item)

    @property
    def machine_time_step(self):
        return self._read_config_int("Machine", "machine_time_step")

    @machine_time_step.setter
    def machine_time_step(self, new_value):
        self._config.set("Machine", "machine_time_step", new_value)

    @property
    def time_scale_factor(self):
        return self._read_config_int("Machine", "time_scale_factor")

    @time_scale_factor.setter
    def time_scale_factor(self, new_value):
        self._config.set("Machine", "time_scale_factor", new_value)

    def set_up_timings(self, machine_time_step=None, time_scale_factor=None):
        """ Set up timings of the machine

        :param machine_time_step:\
            An explicitly specified time step for the machine.  If None,\
            the value is read from the config
        :param time_scale_factor:\
            An explicitly specified time scale factor for the simulation.\
            If None, the value is read from the config
        """

        # set up timings
        if machine_time_step is not None:
            self.machine_time_step = machine_time_step

        if self.machine_time_step <= 0:
            raise ConfigurationException(
                "invalid machine_time_step {}: must greater than zero".format(
                    self.machine_time_step))

        if time_scale_factor is not None:
            self.time_scale_factor = time_scale_factor

    @staticmethod
    def _make_dirs(path):
        # Workaround for Python 2/3 Compatibility (Python 3 raises on exists)
        try:
            os.makedirs(path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
