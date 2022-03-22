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

import logging
from spinn_utilities.log import FormatAdapter
from spinn_utilities.log_store import LogStore
from spinn_utilities.overrides import overrides
from .provenance_writer import ProvenanceWriter
from .provenance_reader import ProvenanceReader

logger = FormatAdapter(logging.getLogger(__name__))


class LogStoreDB(LogStore):

    @overrides(LogStore.store_log)
    def store_log(self, level, message):
        with ProvenanceWriter() as db:
            db.store_log(level, message)

    @overrides(LogStore.retreive_log_messages)
    def retreive_log_messages(self, min_level=0):
        return ProvenanceReader().retreive_log_messages(min_level)

    @overrides(LogStore.get_location)
    def get_location(self):
        return ProvenanceReader.get_last_run_database_path()

