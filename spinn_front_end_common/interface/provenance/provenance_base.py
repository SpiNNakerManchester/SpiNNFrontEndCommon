# Copyright (c) 2022 The University of Manchester
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

import os
from spinn_front_end_common.data import FecDataView


class ProvenanceBase(object):
    """
    Provides a few class method utils for Provenance files
    """

    __slots__ = []

    @classmethod
    def get_last_run_database_path(cls):
        """ Get the path of the current provenance database of the last run

        .. warning::
            Calling this method between start/reset and run may result in a
            path to a database not yet created.

        :raises ValueError:
            if the system is in a state where path can't be retrieved,
            for example before run is called
        """
        return os.path.join(
            FecDataView.get_provenance_dir_path(), "provenance.sqlite3")

    @classmethod
    def get_last_global_database_path(cls):
        """ Get the path of the current provenance database of the last run

        .. warning::
            Calling this method between start/reset and run may result in a
            path to a database not yet created.

        :raises ValueError:
            if the system is in a state where path can't be retrieved,
            for example before run is called
        """
        return os.path.join(
            FecDataView.get_timestamp_dir_path(), "global_provenance.sqlite3")
