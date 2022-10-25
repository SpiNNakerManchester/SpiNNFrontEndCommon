# Copyright (c) 2017-2022 The University of Manchester
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

import sqlite3
from spinn_utilities.log_store import LogStore
from spinn_utilities.overrides import overrides
from .global_provenance import GlobalProvenance
from .provenance_reader import ProvenanceReader


class LogStoreDB(LogStore):

    @overrides(LogStore.store_log)
    def store_log(self, level, message, timestamp=None):
        try:
            with GlobalProvenance() as db:
                db.store_log(level, message, timestamp)
        except sqlite3.OperationalError as ex:
            if "database is locked" in ex.args:
                # Ok ignore this one
                # DO NOT log this error here or you will loop forever!
                return
            # all others are bad
            raise

    @overrides(LogStore.retreive_log_messages)
    def retreive_log_messages(self, min_level=0):
        with GlobalProvenance() as db:
            return db.retreive_log_messages(min_level)

    @overrides(LogStore.get_location)
    def get_location(self):
        return GlobalProvenance.get_global_provenace_path()
