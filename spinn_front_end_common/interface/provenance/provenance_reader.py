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

    By default this will wrap around the database used to store the
    provenance of the last run. The path is not updated so this reader is
    not effected by a reset or an end

    The assumption is that the database is in the current provenance format.
    This inlcudes both that DDL statements used to create the database but
    also the underlying database structure. Currenlty sqllite3

    .. warning::
        This class is only a wrapper around the database file so if the file
        is deleted the class will no longer work.

    """

    __slots__ = ["_provenance_data_path"]

    @staticmethod
    def get_last_run_database_path():
        """ Get the path of the current provenance database of the last run

       .. warning::
            Calling this method between start/reset and run may result in a
            path to a database not yet created.

        :raises ValueError:
            if the system is in a state where path can't be retrieved,
            for example before run is called
        """
        provenance_data_path = globals_variables.provenance_file_path()
        return os.path.join(provenance_data_path, PROVENANCE_DB)

    def __init__(self, provenance_data_path=None):
        """
        Create a wrapper around the database.

        The suggested way to call this is without the path param allowing
        get_last_run_database_path to find the correct path

        :param provenance_data_path: Path to the provenace database to wrap
        :type provenance_data_path: None or str
        """
        if provenance_data_path:
            self._provenance_data_path = provenance_data_path
        else:
            self._provenance_data_path = self.get_last_run_database_path()

    def get_database_handle(self, read_only=True, use_sqlite_rows=False):
        """
        Gets a handle to the open database.

        .. note::
            This method is mainly provided as a support method for the later
            methods that return specific data. For new IntergationTests
            please add a specific method rather than call this directly.

        .. warning::
            It is the callers responsibility to close the database.
            The recommended usage is therefor a with statement

        :param read_only: If true will return a readonly database
        :type read_only: None or bool
        :param use_sqlite_rows:
        If true the results of run_query will be Sqlite3 rows.
        If False the results of run_query will be unnamed tuples.
        :type use_sqlite_rows: None or bool
        :return: an Open sqlite3 connection
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

    def run_query(
            self, query, params=None, read_only=True, use_sqlite_rows=False):
        """
        Opens a connection to the database, runs a query, extracts the results
        and closes the connection

        The return type depends on the use_sqlite_rows param.
        By default this method returns tuples

        This method will not allow queries that change the database unless the
        read_only flag is set to False.

        .. note::
            This method is mainly provided as a support method for the later
            methods that return specific data. For new IntergationTests
            please add a specific method rather than call this directly.

        :param str query: The sql query to be run. May include ? wildcards
        :param params: In iterable of the values to replace the ? wildacrds
            with. The number and types must match what the query expects
        :param read_only: see get_database_handle
        :type read_only: None or bool
        :param use_sqlite_rows: see get_database_handle
        :type use_sqlite_rows: None or bool
        :return: A list possibly empty of tuples/rows
        (one for each row in the database)
        where the number and tyoe of the values cooresponds to the where
        statement
        """
        if params is None:
            params = []
        if not os.path.exists(self._provenance_data_path):
            raise Exception("no such DB: " + self._provenance_data_path)
        with self.get_database_handle(read_only, use_sqlite_rows) as db:
            results = []
            for row in db.execute(query, params):
                results.append(row)
        return results

    def cores_with_late_spikes(self):
        """
        Gets the x, y, p and count of the cores where late spikes arrived.

        Cores that received spikes but where none where late are NOT included.

        :return: A list hopefully empty of tuples (x, y, p , count) of cores
        where their where late arrving spikes.
        :rtype: list(tuple(int, int, int , int))
        """
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
            results.append("{}: {}\n".format(row[0], row[1]))
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
    # This only works if there is a local sql file in the directory
    pr = ProvenanceReader("provenance.sqlite3")
    query = """
        SELECT the_value
        FROM provenance_view
        WHERE description_name = 'Local_P2P_Packets'
        """
    results = pr.run_query(query)
    for row in results:
        print(row)
    print(pr.cores_with_late_spikes())
    print(pr.get_run_time_of_BufferExtractor())
