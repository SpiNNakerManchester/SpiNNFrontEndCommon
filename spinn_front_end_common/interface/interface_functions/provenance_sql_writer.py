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
from spinn_front_end_common.interface.provenance import SqlLiteDatabase
from spinn_front_end_common.utilities.constants import PROVENANCE_DB


class ProvenanceSQLWriter(object):
    """ Writes provenance in SQL format.
    """

    __slots__ = []

    def __call__(self, provenance_data_items, provenance_data_path):
        """ Writes provenance in SQL format

        :param list(ProvenanceDataItem) provenance_data_items:
        :param str provenance_data_path:
        """
        database_file = os.path.join(
            provenance_data_path, PROVENANCE_DB)
        with SqlLiteDatabase(database_file) as db:
            db.insert_items(provenance_data_items)
