# Copyright (c) 2021 The University of Manchester
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
from typing import Iterable, List, Optional, Sequence, Tuple, cast
from typing_extensions import TypeAlias
from spinn_utilities.typing.coords import XYP
from spinn_front_end_common.utilities.base_database import (
    BaseDatabase, _SqliteTypes)

#: Basic types supported natively by SQLite
_MonitorItem: TypeAlias = Tuple[int, int, _SqliteTypes]
_RouterItem: TypeAlias = Tuple[int, int, int]


class ProvenanceReader(BaseDatabase):
    """
    Provides a connection to a database containing provenance for the current
    run and some convenience methods for extracting provenance data from it.

    By default this will wrap around the database used to store the
    provenance of the last run. The path is not updated so this reader is
    not effected by a reset or an end.

    The assumption is that the database is in the current provenance format.
    This includes both that DDL statements used to create the database but
    also the underlying database structure (currently sqlite3)

    .. warning::
        This class is only a wrapper around the database file so if the file
        is deleted the class will no longer work.
    """

    __slots__ = ()

    def __init__(self, provenance_data_path: Optional[str] = None):
        """
        Create a wrapper around the database.

        The suggested way to call this is *without* the
        ``provenance_data_path`` parameter, allowing
        :py:meth:`get_last_run_database_path` to find the correct path.

        :param provenance_data_path: Path to the provenance database to wrap
        """
        super().__init__(provenance_data_path, read_only=True,
                         row_factory=None, text_factory=None)

    def run_query(self, query: str, params: Iterable[_SqliteTypes] = ()
                  ) -> List[Sequence[_SqliteTypes]]:
        """
        Opens a connection to the database, runs a query, extracts the results
        and closes the connection.

        The return type depends on the use_sqlite_rows parameter.
        By default this method returns tuples (lookup by index) but the
        advanced tuple type can be used instead, which supports lookup by name
        used in the query (use ``AS name`` in the query to set).

        This method will not allow queries that change the database unless the
        read_only flag is set to False.

        .. note::
            This method is mainly provided as a support method for the later
            methods that return specific data. For new IntergationTests
            please add a specific method rather than call this directly.

        :param query: The SQL query to be run. May include ``?`` wildcards
        :param params:
            The values to replace the ``?`` wildcards with.
            The number and types must match what the query expects
        :return: A list possibly empty of tuples/rows
            (one for each row in the database)
            where the number and type of the values corresponds to the where
            statement
        """
        return list(self.cursor().execute(query, list(params)))

    def cores_with_late_spikes(self) -> List[Tuple[int, int, int, int]]:
        """
        Gets the x, y, p and count of the cores where late spikes arrived.

        Cores that received spikes but where none were late are *not* included.

        :return: A list hopefully empty of tuples (x, y, p, count) of cores
            where their where late arriving spikes.
        """
        query = """
            SELECT x, y, p, the_value AS "value"
            FROM core_provenance
            WHERE description = 'Number_of_late_spikes'
                AND the_value > 0
            """
        return cast(List[Tuple[int, int, int, int]], self.run_query(query))

    def get_provenance_for_router(self, x: int, y: int) -> str:
        """
        Gets the provenance item(s) from the last run relating to a chip.

        :param x: The X coordinate of the chip
        :param y: The Y coordinate of the chip
        :return:
            A possibly multi-line string with for each row which matches the
            like a line ``description_name: value``
        """
        query = """
            SELECT
                description,
                sum(the_value) AS "value"
            FROM router_provenance
            WHERE x = ? AND y = ?
            GROUP BY description
            ORDER BY description
            """
        return "\n".join(
            f"{cast(str, row[0])}: {cast(int, row[1])}"
            for row in self.run_query(query, [int(x), int(y)]))

    def get_cores_with_provenace(self) -> List[XYP]:
        """
        Gets the cores with provenance.

        :return: A list tuples (x, y, p)
        """
        query = """
            SELECT core_name, x, y, p
            FROM core_provenance_view
            group by x, y, p
            """
        return cast(List[XYP], self.run_query(query))

    def get_router_by_chip(self, description: str) -> List[_RouterItem]:
        """
        Gets the router values for a specific item.

        :param description:
        :return: list of tuples (x, y, value)
        """
        query = """
            SELECT x, y, the_value
            FROM router_provenance
            WHERE description = ?
            """
        data = self.run_query(query, [description])
        try:
            return cast(List[_RouterItem], data)
        except IndexError:
            return []

    def get_monitor_by_chip(self, description: str) -> List[_MonitorItem]:
        """
        Gets the monitor values for a specific item.

        :param description:
        :return: list of tuples x, y, value)
        """
        query = """
            SELECT x, y, the_value
            FROM monitor_provenance
            WHERE description = ?
            """
        data = self.run_query(query, [description])
        try:
            return cast(List[_MonitorItem], data)
        except IndexError:
            return []

    def messages(self) -> List[str]:
        """
        List all the provenance messages.

        :return: all messages logged or not; order is whatever the DB chooses
        """
        query = """
             SELECT message
             FROM reports
             """
        return [cast(str, msg) for msg, in self.run_query(query, [])]

    @staticmethod
    def demo() -> None:
        """
        A demonstration of how to use this class.

        See also `unittests/interface/provenance/test_provenance_database.py`
        """
        # This uses the example file in the same directory as this script
        with ProvenanceReader(os.path.join(
                os.path.dirname(__file__), "provenance.sqlite3")) as pr:
            print("DIRECT QUERY:")
            query = """
                SELECT x, y, the_value
                FROM router_provenance
                WHERE description = 'Local_P2P_Packets'
                """
            results = pr.run_query(query)
            for row in results:
                print(row)
            print("\nCORES WITH LATE SPIKES:")
            print(pr.cores_with_late_spikes())
            print("\nROUTER (0,0) PROVENANCE:")
            print(pr.get_provenance_for_router(0, 0))
            print("\nCORES WITH PROVENANCE")
            print(pr.get_cores_with_provenace())


if __name__ == '__main__':
    ProvenanceReader.demo()
