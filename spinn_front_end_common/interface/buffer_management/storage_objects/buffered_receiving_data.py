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
from .sqllite_database import BufferDatabase
from spinn_front_end_common.data import FecDataView

#: Name of the database in the data folder
DB_FILE_NAME = "buffer.sqlite3"


class BufferedReceivingData(object):
    """ Stores the information received through the buffering output\
        from the SpiNNaker system.
    """

    __slots__ = [
        #: the AbstractDatabase holding the data to store
        "_db",

        #: the path to the database
        "_db_file",

    ]

    def __init__(self):
        self._db_file = os.path.join(
            FecDataView.get_run_dir_path(), DB_FILE_NAME)
        self._db = None
        self.reset()

    def reset(self):
        """ Perform tasks to restart recording from time=0
        """
        if os.path.exists(self._db_file):
            if self._db:
                self._db.close()
            os.remove(self._db_file)
        self._db = BufferDatabase(self._db_file)

    def store_data_in_region_buffer(self, x, y, p, region, missing, data):
        """ Store some information in the correspondent buffer class for a\
            specific chip, core and region.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int region: Region containing the data to be stored
        :param bool missing: Whether any data is missing
        :param bytearray data: data to be stored
        """
        # pylint: disable=too-many-arguments
        self._db.store_data_in_region_buffer(x, y, p, region, missing, data)

    def get_region_data(self, x, y, p, region):
        """ Get the data stored for a given region of a given core.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int region: Region containing the data
        :return: a buffer containing all the data received during the
            simulation, and a flag indicating if any data was missing
        :rtype: tuple(memoryview, bool)
        """
        return self._db.get_region_data(x, y, p, region)

    def clear(self, x, y, p, region_id):
        """ Clears the data from a given data region (only clears things\
            associated with a given data recording region).

        :param int x: placement x coordinate
        :param int y: placement y coordinate
        :param int p: placement p coordinate
        :param int region_id: the recording region ID to clear data from
        :rtype: None
        """
        self._db.clear_region(x, y, p, region_id)
