# Copyright (c) 2021 The University of Manchester
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
import contextlib
import errno
import logging
import os
from spinn_utilities.log import FormatAdapter
_logger = FormatAdapter(logging.getLogger(__name__))


class ReportFile(contextlib.AbstractContextManager):
    def __init__(self, report_dir, file_name, logger=None):
        self._file_name = os.path.join(report_dir, file_name)
        self._logger = logger if logger else _logger
        self._f = None

    def __enter__(self):
        try:
            self._f = open(self._file_name, "w")
        except IOError:
            self._logger.exception(
                "Generate_placement_reports: "
                "Can't open file {} for writing.", self._file_name)
            self._f = open(os.devnull, "w")
        return self._f

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self._f.close()
        except IOError:
            self._logger.exception(
                "Generate_placement_reports: "
                "Can't close file {}, opened for writing.", self._file_name)
        return None


class ReportDir:
    def __init__(self, report_dir, subdir, logger=None):
        self._dir_name = os.path.join(report_dir, subdir)
        self._logger = logger
        try:
            os.mkdir(self._dir_name)
        except IOError as e:
            if e.errno != errno.EEXIST:
                raise

    def file(self, file_name):
        return ReportFile(self._dir_name, file_name, self._logger)
