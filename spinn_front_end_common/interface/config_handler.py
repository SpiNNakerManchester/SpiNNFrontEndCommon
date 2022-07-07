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

from configparser import NoOptionError
import datetime
import logging
import os
import errno
import shutil
import time
from spinn_utilities.log import FormatAdapter
from spinn_machine import Machine
from spinn_utilities.config_holder import (
    config_options, load_config, get_config_bool, get_config_int,
    get_config_str, get_config_str_list, set_config)
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION)
from spinn_front_end_common.utilities.exceptions import ConfigurationException

logger = FormatAdapter(logging.getLogger(__name__))

APP_DIRNAME = 'application_generated_data_files'
FINISHED_FILENAME = "finished"
ERRORED_FILENAME = "errored"
REPORTS_DIRNAME = "reports"
TIMESTAMP_FILENAME = "time_stamp"
WARNING_LOGS_FILENAME = "warning_logs.txt"

# options names are all lower without _ inside config
_DEBUG_ENABLE_OPTS = frozenset([
    "reportsenabled",
    "clear_iobuf_during_run", "extract_iobuf"])
_REPORT_DISABLE_OPTS = frozenset([
    "clear_iobuf_during_run", "extract_iobuf"])


class ConfigHandler(object):
    """ Superclass of AbstractSpinnakerBase that handles function only \
        dependent of the config and the order its methods are called.
    """

    __slots__ = [
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

        # The machine timestep, in microseconds
        "__machine_time_step",

        # The machine timestep, in milliseconds
        # Semantic sugar for __machine_time_step / 1000
        "__machine_time_step_ms",

        # The number of machine timestep in a milliseconds
        # Semantic sugar for 1000 / __machine_time_step
        "__machine_time_step_per_ms",

        # The time scaling factor.
        "__time_scale_factor"
    ]

    def __init__(self):
        load_config()

        # set up machine targeted data
        self._use_virtual_board = get_config_bool("Machine", "virtual_board")
        self._debug_configs()
        self._previous_handler()

        # Pass max_machine_cores to Machine so if effects everything!
        max_machine_core = get_config_int("Machine", "max_machine_core")
        if max_machine_core is not None:
            Machine.set_max_cores_per_chip(max_machine_core)

        self._json_folder = None
        self._provenance_file_path = None
        self._report_default_directory = None
        self._report_simulation_top_directory = None
        self._this_run_time_string = None
        self.__machine_time_step = None
        self.__machine_time_step_ms = None
        self.__time_scale_factor = None
        self._app_provenance_file_path = None
        self._system_provenance_file_path = None

    def _debug_configs(self):
        """ Adjust and checks config based on mode and reports_enabled

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
        elif not get_config_bool("Reports", "reportsEnabled"):
            for option in config_options("Reports"):
                # options names are all lower without _ inside config
                if option in _REPORT_DISABLE_OPTS or option[:5] == "write":
                    if not get_config_bool("Reports", option):
                        set_config("Reports", option, "False")
                        logger.info(
                            "As reportsEnabled == \"False\", [Reports] {} "
                            "has been set to False", option)
        if self._use_virtual_board:
            # TODO handle in the execute methods
            if get_config_bool("Reports", "write_energy_report"):
                set_config("Reports", "write_energy_report", "False")
                logger.info("[Reports]write_energy_report has been set to "
                            "False as using virtual boards")

    def _previous_handler(self):
        self._error_on_previous("loading_algorithms")
        self._error_on_previous("application_to_machine_graph_algorithms")
        self._error_on_previous("machine_graph_to_machine_algorithms")
        self._error_on_previous("machine_graph_to_virtual_machine_algorithms")

    def _error_on_previous(self, option):
        try:
            get_config_str_list("Mapping", option)
        except NoOptionError:
            # GOOD!
            return
        raise ConfigurationException(
            f"cfg setting {option} is no longer supported! "
            "See https://spinnakermanchester.github.io/common_pages/"
            "Algorithms.html.")

    def _adjust_config(self, runtime,):
        """ Adjust and checks config based on runtime

        :param runtime:
        :type runtime: int or bool
        :param frozenset(str) debug_enable_opts:
        :param frozenset(str) report_disable_opts:
        :raises ConfigurationException:
        """
        if runtime is None:
            if get_config_bool("Reports", "write_energy_report"):
                set_config("Reports", "write_energy_report", "False")
                logger.info("[Reports]write_energy_report has been set to "
                            "False as runtime is set to forever")

    def child_folder(self, parent, child_name, must_create=False):
        """
        :param str parent:
        :param str child_name:
        :param bool must_create:
            If `True`, the directory named by `child_name` (but not necessarily
            its parents) must be created by this call, and an exception will be
            thrown if this fails.
        :return: The fully qualified name of the child folder.
        :rtype: str
        :raises OSError: if the directory existed ahead of time and creation
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

    def _remove_excess_folders(
            self, max_kept, starting_directory, remove_errored_folders):
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
                    errored_flag = os.path.join(os.path.join(
                        starting_directory, current_oldest_file),
                        ERRORED_FILENAME)
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

    def _set_up_report_specifics(self, n_calls_to_run):
        """
        :param int n_calls_to_run:
            the counter of how many times run has been called.
        """

        default_report_file_path = get_config_str(
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
                get_config_int("Reports", "max_reports_kept"),
                report_default_directory,
                get_config_bool("Reports", "remove_errored_folders"))

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
        with open(time_of_run_file_name, "w", encoding="utf-8") as f:
            f.writelines(self._this_run_time_string)

        if get_config_bool("Logging", "warnings_at_end_to_file"):
            log_report_file = os.path.join(
                self._report_default_directory, WARNING_LOGS_FILENAME)
            logger.set_report_File(log_report_file)

    @staticmethod
    def __make_timestamp():
        now = datetime.datetime.now()
        return "{:04}-{:02}-{:02}-{:02}-{:02}-{:02}-{:02}".format(
            now.year, now.month, now.day,
            now.hour, now.minute, now.second, now.microsecond)

    def _set_up_output_folders(self, n_calls_to_run):
        """ Sets up all outgoing folders by creating a new timestamp folder
            for each and clearing

        :param int n_calls_to_run:
            the counter of how many times run has been called.
        :rtype: None
        """

        # set up reports default folder
        self._set_up_report_specifics(n_calls_to_run)

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

    def __write_named_file(self, file_name):
        app_file_name = os.path.join(
            self._report_simulation_top_directory, file_name)
        with open(app_file_name, "w", encoding="utf-8") as f:
            f.writelines("file_name")

    def write_finished_file(self):
        """ Write a finished file that allows file removal to only remove
            folders that are finished.
            :rtype: None
        """
        self.__write_named_file(FINISHED_FILENAME)

    def write_errored_file(self):
        """ Writes a errored file that allows file removal to only remove \
            folders that are errored if requested to do so
        :rtype:
        """
        self.__write_named_file(ERRORED_FILENAME)

    def set_up_timings(self, machine_time_step=None, time_scale_factor=None):
        """ Set up timings of the machine

        :param machine_time_step:
            An explicitly specified time step for the machine.  If None,
            the value is read from the config
        :type machine_time_step: int or None
        :param time_scale_factor:
            An explicitly specified time scale factor for the simulation.
            If None, the value is read from the config
        :type time_scale_factor: int or None
        """

        # set up timings
        if machine_time_step is None:
            self.machine_time_step = get_config_int(
                "Machine", "machine_time_step")
        else:
            self.machine_time_step = machine_time_step

        if self.__machine_time_step <= 0:
            raise ConfigurationException(
                f'invalid machine_time_step {self.__machine_time_step}'
                f': must greater than zero')

        if time_scale_factor is None:
            # Note while this reads from the cfg the cfg default is None
            self.__time_scale_factor = get_config_int(
                "Machine", "time_scale_factor")
        else:
            self.__time_scale_factor = time_scale_factor

    @property
    def machine_time_step(self):
        """ The machine timestep, in microseconds

        :rtype: int
        """
        return self.__machine_time_step

    @property
    def machine_time_step_ms(self):
        """ The machine timestep, in milli_seconds

        :rtype: float
        """
        return self.__machine_time_step_ms

    @property
    def machine_time_step_per_ms(self):
        """ The machine timesteps in a milli_second

        :rtype: float
        """
        return self.__machine_time_step_per_ms

    @machine_time_step.setter
    def machine_time_step(self, new_value):
        """

        :param new_value: Machine timestep in microseconds
        """
        self.__machine_time_step = new_value
        self.__machine_time_step_ms = (
                new_value / MICRO_TO_MILLISECOND_CONVERSION)
        self.__machine_time_step_per_ms = (
                MICRO_TO_MILLISECOND_CONVERSION / new_value)

    @property
    def time_scale_factor(self):
        """ The time scaling factor.
        :rtype: int
        """
        return self.__time_scale_factor

    @time_scale_factor.setter
    def time_scale_factor(self, new_value):
        self.__time_scale_factor = new_value

    @staticmethod
    def _make_dirs(path):
        # Workaround for Python 2/3 Compatibility (Python 3 raises on exists)
        try:
            os.makedirs(path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
