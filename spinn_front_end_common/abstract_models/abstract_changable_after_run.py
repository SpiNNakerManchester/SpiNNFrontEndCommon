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
from spinn_utilities.abstract_base import (
    AbstractBase, abstractmethod)


@add_metaclass(AbstractBase)
class AbstractChangableAfterRun(object):
    """ An item that can be changed after a call to run, the changes to which\
        might or might not require mapping or data generation.
    """

    __slots__ = ()

    @property
    def requires_mapping(self):
        """ True if changes that have been made require that mapping be\
            performed.  By default this returns False but can be overridden to\
            indicate changes that require mapping.

        :rtype: bool
        """
        return False

    @property
    def requires_data_generation(self):
        """ True if changes that have been made require that data generation\
            be performed.  By default this returns False but can be overridden\
            to indicate changes that require data regeneration.

        :rtype: bool
        """
        return False

    @abstractmethod
    def mark_no_changes(self):
        """ Marks the point after which changes are reported, so that new\
            changes can be detected before the next check.
        """
