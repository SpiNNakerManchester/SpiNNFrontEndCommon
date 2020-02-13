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

import os
from spinn_front_end_common.interface.interface_functions import (
    ProvenanceJSONWriter, ProvenanceSQLWriter, ProvenanceXMLWriter)
from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem


def _create_provenenace():
    items = []
    items.append(ProvenanceDataItem(["core1", "value1"], 23))
    items.append(ProvenanceDataItem(["core1", "value2"], 45))
    items.append(ProvenanceDataItem(["core1", "value3"], 67))
    items.append(ProvenanceDataItem(["core2", "value1"], "bacon"))
    items.append(ProvenanceDataItem(["core2", "value2"], 23))
    items.append(ProvenanceDataItem(["core2", "value3"], 45))
    return items


def test_json():
    provenance_data_path = "test_output"
    for filename in os.listdir(provenance_data_path):
        _, file_extension = os.path.splitext(filename)
        if file_extension == ".json":
            os.remove(os.path.join(provenance_data_path, filename))
    provenance_data_items = _create_provenenace()
    writer = ProvenanceJSONWriter()
    writer(provenance_data_items, provenance_data_path)


def test_xml():
    provenance_data_path = "test_output"
    for filename in os.listdir(provenance_data_path):
        _, file_extension = os.path.splitext(filename)
        if file_extension == ".xml":
            os.remove(os.path.join(provenance_data_path, filename))
    provenance_data_items = _create_provenenace()
    writer = ProvenanceXMLWriter()
    writer(provenance_data_items, provenance_data_path)


def test_database():
    provenance_data_path = "test_output"
    for filename in os.listdir(provenance_data_path):
        _, file_extension = os.path.splitext(filename)
        if file_extension == ".sqlite3":
            os.remove(os.path.join(provenance_data_path, filename))
    provenance_data_items = _create_provenenace()
    writer = ProvenanceSQLWriter()
    writer(provenance_data_items, provenance_data_path)
