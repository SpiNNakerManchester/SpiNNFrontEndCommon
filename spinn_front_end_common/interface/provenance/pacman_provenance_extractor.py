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

from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem


class PacmanProvenanceExtractor(object):
    """ Extracts Provenance data from a :py:class:`PACMANAlgorithmExecutor`
    """

    TOP_NAME = "pacman"

    __slots__ = ["__data_items", "__already_done"]

    def __init__(self):
        self.__data_items = list()
        self.__already_done = set()

    def extract_provenance(self, executor):
        """ Acquires the timings from PACMAN algorithms (provenance data)

        :param ~pacman.executor.PACMANAlgorithmExecutor executor:
            the PACMAN workflow executor
        :rtype: None
        """
        for (algorithm, run_time, exec_names) in executor.algorithm_timings:
            key = "run_time_of_{}".format(algorithm)
            if key not in self.__already_done:
                names = [self.TOP_NAME, exec_names, key]
                self.__data_items.append(ProvenanceDataItem(names, run_time))
                self.__already_done.add(key)

    @property
    def data_items(self):
        """ Returns the provenance data items

        :return: the provenance items
        :rtype: iterable(ProvenanceDataItem)
        """
        return self.__data_items

    def clear(self):
        """ Clears the provenance data store

        :rtype: None
        """
        self.__data_items = list()
        self.__already_done = set()
