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

from spinn_utilities.abstract_base import AbstractBase, abstractmethod


class AbstractMachineAllocationController(object, metaclass=AbstractBase):
    """ An object that controls the allocation of a machine
    """

    __slots__ = ()

    @abstractmethod
    def extend_allocation(self, new_total_run_time):
        """ Extend the allocation of the machine from the original run time.

        :param float new_total_run_time:
            The total run time that is now required starting from when the
            machine was first allocated
        """

    @abstractmethod
    def close(self):
        """ Indicate that the use of the machine is complete.
        """

    @abstractmethod
    def where_is_machine(self, chip_x, chip_y):
        """ Locates and returns cabinet, frame, board for a given chip in a\
            machine allocated to this job.

        :param int chip_x: chip x location
        :param int chip_y: chip y location
        :return: (cabinet, frame, board)
        :rtype: tuple(int,int,int)
        """
