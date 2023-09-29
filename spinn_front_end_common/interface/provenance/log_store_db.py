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
from .global_provenance import GlobalProvenance


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
