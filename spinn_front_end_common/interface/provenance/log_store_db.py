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

from datetime import datetime
import sqlite3
from typing import List, Optional

from spinn_utilities.config_holder import configs_loaded
from spinn_utilities.log_store import LogStore
from spinn_utilities.overrides import overrides
from .global_provenance import GlobalProvenance


class LogStoreDB(LogStore):
    """
    Log message storage mechanism that uses a database.
    """
    __slots__ = ()

    @overrides(LogStore.store_log)
    def store_log(
            self, level: int, message: str,
            timestamp: Optional[datetime] = None) -> None:
        if configs_loaded():
            try:
                with GlobalProvenance() as db:
                    db.store_log(level, message, timestamp)
            except sqlite3.OperationalError as ex:
                if "database is locked" in ex.args:
                    # OK ignore this one
                    # DO NOT log this error here or you will loop forever!
                    return
                # all others are bad
                raise
        else:
            # Only expected to happen when running parallel tests
            print("store logs skipped as configs not loaded.")

    @overrides(LogStore.retreive_log_messages)
    def retreive_log_messages(
            self, min_level: int = 0) -> List[str]:
        with GlobalProvenance() as db:
            return db.retreive_log_messages(min_level)

    @overrides(LogStore.get_location)
    def get_location(self) -> str:
        return GlobalProvenance.get_global_provenace_path()
