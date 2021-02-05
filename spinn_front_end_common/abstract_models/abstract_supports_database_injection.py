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

from spinn_utilities.abstract_base import AbstractBase, abstractproperty
from pacman.model.graphs.machine import MachineVertex
from spinn_front_end_common.utilities.class_utils import check_class_type


class AbstractSupportsDatabaseInjection(object, metaclass=AbstractBase):
    """ Marks a machine vertex as supporting injection of information via a\
        database running on the controlling host.
    """

    __slots__ = ()

    def __init_subclass__(cls, **kwargs):  # @NoSelf
        check_class_type(cls, MachineVertex)
        super().__init_subclass__(**kwargs)

    @abstractproperty
    def is_in_injection_mode(self):
        """ Whether this vertex is actually in injection mode.

        :rtype: bool
        """
