# Copyright (c) 2017 The University of Manchester
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

import sqlite3
from spinn_utilities.log_store import LogStore
from spinn_utilities.overrides import overrides
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import GlobalProvenance
from spinn_front_end_common.utilities.exceptions import DatabaseException


class LogStoreDB(LogStore):

    @overrides(LogStore.store_log)
    def store_log(self, level, message, timestamp=None):
        try:
            try:
                # If in the same thread the view version can be used
                with FecDataView.get_global_database() as db:
                    db.store_log(level, message, timestamp)
            except sqlite3.ProgrammingError:
                # If in a different thread try again with different db
                with GlobalProvenance() as db:
                    db.store_log(level, message, timestamp)
        except sqlite3.OperationalError as ex:
            if "database is locked" in ex.args:
                # Ok ignore this one
                # DO NOT log this error here or you will loop forever!
                return
            # all others are bad
            raise
        except DatabaseException as ex:
            if "double cursor" in ex.args:
                # Ok ignore this one
                # DO NOT log this error here or you will loop forever!
                return
            # all others are bad
            raise

    @overrides(LogStore.retreive_log_messages)
    def retreive_log_messages(self, min_level=0):
        with FecDataView.get_global_database() as db:
            return db.retreive_log_messages(min_level)

    @overrides(LogStore.get_location)
    def get_location(self):
        return FecDataView.get_global_database().get_global_provenace_path()
