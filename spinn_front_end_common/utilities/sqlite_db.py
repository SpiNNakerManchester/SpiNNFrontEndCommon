# Copyright (c) 2017-2021 The University of Manchester
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

from contextlib import AbstractContextManager as ACMBase
import os
import pathlib
import sqlite3
from spinn_utilities.abstract_context_manager import AbstractContextManager


class SQLiteDB(AbstractContextManager):
    """ General support class for SQLite databases.
    """

    __slots__ = [
        # the database holding the data to store
        "__db",
    ]

    def __init__(self, database_file=None, *, read_only=False, ddl_file=None,
                 row_factory=sqlite3.Row, text_factory=memoryview):
        """
        :param str database_file:
            The name of a file that contains (or will contain) an SQLite
            database holding the data. If omitted, an unshared in-memory
            database will be used (suitable only for testing).
        :param bool read_only:
        :param str ddl_file:
        :param ~collections.abc.Callable row_factory:
        :param ~collections.abc.Callable text_factory:
        """
        if database_file is None:
            self.__db = sqlite3.connect(":memory:")  # Magic name!
            # in-memory DB is never read-only
        elif read_only:
            if not os.path.exists(database_file):
                raise FileNotFoundError(f"no such DB: {database_file}")
            db_uri = pathlib.Path(os.path.abspath(database_file)).as_uri()
            self.__db = sqlite3.connect(f"{db_uri}?mode=ro", uri=True)
        else:
            self.__db = sqlite3.connect(database_file)
        if row_factory:
            self.__db.row_factory = row_factory
        if text_factory:
            self.__db.text_factory = text_factory
        if ddl_file:
            with open(ddl_file) as f:
                sql = f.read()
            self.__db.executescript(sql)

    def __del__(self):
        self.close()

    def close(self):
        """ Finalises and closes the database.
        """
        if self.__db is not None:
            self.__db.close()
            self.__db = None

    @property
    def db(self):
        """ The underlying SQLite database connection.

        :rtype: ~sqlite3.Connection
        :raises AttributeError: if the database connection has been closed
        """
        if not self.__db:
            raise AttributeError("database has been closed")
        return self.__db

    def transaction(self, isolation_level=None):
        """ Get a context manager that manages a transaction on the database.\
        The value of the context manager is a :py:class:`~sqlite3.Cursor`.\
        This means you can do this::

            with db.transaction() as cursor:
                cursor.execute(...)

        :param str isolation_level:
            The transaction isolation level;
            note that this sets it for the connection!
        """
        db = self.db
        if isolation_level:
            db.isolation_level = isolation_level
        return _DbWrapper(db)


class _DbWrapper(ACMBase):
    def __init__(self, db):
        self.__d = db

    def __enter__(self):
        self.__d.__enter__()
        return self.__d.cursor()

    def __exit__(self, exc_type, exc_value, traceback):
        return self.__d.__exit__(exc_type, exc_value, traceback)
