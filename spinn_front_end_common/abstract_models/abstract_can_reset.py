# Copyright (c) 2019 The University of Manchester
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

from spinn_utilities.abstract_base import (
    AbstractBase, abstractmethod)


class AbstractCanReset(object, metaclass=AbstractBase):
    """ Indicates an object that can be reset to time 0.

    This is used when AbstractSpinnakerBase.reset is called.
    All Vertices and all edges in the original graph
    (the one added to by the user) will be checked and reset.
    """
    __slots__ = []

    @abstractmethod
    def reset_to_first_timestep(self):
        """ Reset the object to first time step.
        """
