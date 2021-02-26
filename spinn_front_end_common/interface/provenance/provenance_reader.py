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

import os
from spinn_front_end_common.utilities import globals_variables
from spinn_front_end_common.utilities.constants import PROVENANCE_DB
import sqlite3


class ProvenanceReader(object):
    """
    Provides a connection to a sqllite3 database and some provenenace
    convenience methods

    """

    __slots__ = ["_provenance_data_path"]

    @staticmethod
    def get_last_run_database_path():
        """ Get the path of the current provenance database of the last run

       .. warning::
            Calling this method before run is called can lead to unexpected
            results and is not supported.
            Especially between reset and run it could return either
            the provenance of the previous run or for the next run.

        :raises ValueError:
            if the system is in a state where path can't be retrieved,
            for example before run is called
        """
        provenance_data_path = globals_variables.provenance_file_path()
        return os.path.join(provenance_data_path, PROVENANCE_DB)

    def __init__(self, provenance_data_path=None):
        if provenance_data_path:
            self._provenance_data_path = provenance_data_path
        else:
            self._provenance_data_path = self.get_last_run_database_path()

    def get_database_handle(self, read_only=True, use_sqlite_rows=False):
        """
        Gets a handle to the open database.

        .. note::
            It is the callers responsibility to close the database.
            The recommended usage is therefor a with statement

        :param bool read_only: If true will return a readonly database
        :param use_sqlite_rows:
        If true the results of run_query will be Sqlite3 rows.
        If False the results of run_query will be unnamed tuples.
        :return: and Open sqlite3 connection
        """
        if not os.path.exists(self._provenance_data_path):
            raise Exception("no such DB: " + self._provenance_data_path)
        if read_only:
            db_path = os.path.abspath(self._provenance_data_path)
            db = sqlite3.connect("file:{}?mode=ro".format(db_path), uri=True)
        else:
            db = sqlite3.connect(self._provenance_data_path)
        # Force case-insensitive matching of provenance names
        db.execute("PRAGMA case_sensitive_like=OFF;")
        if use_sqlite_rows:
            db.row_factory = sqlite3.Row
        return db

    def run_query(self, query, params=None):
        if params is None:
            params = []
        if not os.path.exists(self._provenance_data_path):
            raise Exception("no such DB: " + self._provenance_data_path)
        with self.get_database_handle() as db:
            results = []
            for row in db.execute(query, params):
                results.append(row)
        return results

    def cores_with_late_spikes(self):
        query = """
            SELECT x, y, p, the_value 
            FROM provenance_view 
            WHERE description_name = 'Number_of_late_spikes' 
                AND the_value > 0
            """
        return self.run_query(query)

    def get_provenance(self, description_name):
        """
        Gets the provenance item(s) from the last run

        :param str description_name: The value to LIKE search for in the
        description_name column. Can be the full name have %  amd _ wildcards

        :return: A possibly multiline string with
        for each row which matches the like a line
        description_name: value
        """
        query = """
            SELECT description_name AS description, the_value AS 'value' 
            FROM provenance_view  
            WHERE description_name LIKE ?
            """
        results = []
        for row in self.run_query(query, [description_name]):
            results.append("{}: {}\n".format(row["description"], row["value"]))
        return "".join(results)

    def get_run_time_of_BufferExtractor(self):
        """
        Gets the BufferExtractor provenance item(s) from the last run

        :return: A possibly multiline string with
        for each row which matches the like %BufferExtractor
        description_name: value
        """
        return self.get_provenance("%BufferExtractor")


if __name__ == '__main__':
    pr = ProvenanceReader("/home/brenninc/spinnaker/SpiNNFrontEndCommon/spinn_front_end_common/interface/provenance/provenance.sqlite3")
    query = "SELECT the_value FROM provenance_view WHERE description_name = 'Local_P2P_Packets'"
    results = pr.run_query(query)
    for row in results:
        print(row)
    print(pr.cores_with_late_spikes())
