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

from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractMachineAllocationController(object):
    """ An object that controls the allocation of a machine
    """

    __slots__ = ()

    @abstractmethod
    def allocate_time(self, run_time_in_us):
        """ Add allocation of the machine run time.

        The allocator has to keep track of the total and\
        decide what to do for None (run_forever)

        :param run_time_in_us: The new run time that is now being uses.
        :type run_time_in_us: int or None
        """

    @abstractmethod
    def close(self):
        """ Indicate that the use of the machine is complete.
        """
