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

import logging
import os
from spinn_utilities.config_holder import get_config_int
from spinn_front_end_common.utilities.globals_variables import (
    provenance_file_path)
from spinn_utilities.log import FormatAdapter
logger = FormatAdapter(logging.getLogger(__name__))

_report_count = 0


class ProvenanceDataItem(object):
    """ Container for provenance data
    """
    __slots__ = [
        "_message",
        "_names",
        "_value"]

    def __init__(self, names, value, report=False, message=""):
        """
        :param list(str) names:
            A list of strings representing the naming hierarchy of this item
        :param value: The value of the item
        :type value: int or float or str
        :param bool report: True if the item should be reported to the user
        :param str message:
            The message to send to the end user if report is True
        """
        self._names = names
        self._value = value
        self._message = message
        if report:
            self._add_report()

    @property
    def message(self):
        """ The message to report to the end user, or None if no message

        :rtype: str
        """
        return self._message

    @property
    def names(self):
        """ The hierarchy of names of this bit of provenance data

        :rtype: list(str)
        """
        return self._names

    @property
    def value(self):
        """ The value of the item

        :rtype: int or float or str
        """
        return self._value

    def _add_report(self):
        global _report_count
        report_file = os.path.join(
            provenance_file_path(), "logs")
        with open(report_file, "a") as writer:
            writer.write(self._message)
            writer.write("\n")
        cutoff = get_config_int("Reports", "provenance_report_cutoff")
        if cutoff is None or _report_count < cutoff:
            logger.warning(self._message)
        elif _report_count == cutoff:
            logger.warning(f"Additional interesting provenace items in "
                           f"{report_file}")
        _report_count += 1

    def __repr__(self):
        return "{}:{}:{}:{}".format(
            self._names, self._value, self._report, self._message)

    def __str__(self):
        if self._report:
            return self._message
        return "{}: {}".format(self._names, self._value)
