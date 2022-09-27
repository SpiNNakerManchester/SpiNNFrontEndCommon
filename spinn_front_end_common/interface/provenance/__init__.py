# Copyright (c) 2017-2019 The University of Manchester
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

from .abstract_provides_local_provenance_data import (
    AbstractProvidesLocalProvenanceData)
from .abstract_provides_provenance_data_from_machine import (
    AbstractProvidesProvenanceDataFromMachine)
from .fec_timer import FecTimer
from .log_store_db import LogStoreDB
from .provenance_reader import ProvenanceReader
from .provides_provenance_data_from_machine_impl import (
    ProvidesProvenanceDataFromMachineImpl)
from .provenance_writer import ProvenanceWriter

# TIMER categories
GET_MACHINE = "machine_generation"
MAPPING = "mapping"
DATA_GENERATION = "data_generation"
LOADING = "loading"
RUN_LOOP = "running"
# Algorithm Names used elsewhere
APPLICATION_RUNNER = "Application runner"
BUFFER = "BufferExtraction"

__all__ = ["AbstractProvidesLocalProvenanceData",
           "AbstractProvidesProvenanceDataFromMachine", "LogStoreDB",
           "ProvenanceReader", "ProvenanceWriter",
           "ProvidesProvenanceDataFromMachineImpl"]
