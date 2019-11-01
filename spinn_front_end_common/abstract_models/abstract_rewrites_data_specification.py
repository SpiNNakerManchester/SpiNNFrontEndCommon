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
class AbstractRewritesDataSpecification(object):
    """ Indicates an object that allows data to be changed after run,\
        and so can rewrite the data specification
    """

    __slots__ = ()

    @abstractmethod
    def regenerate_data_specification(self, spec, placement):
        """ Regenerate the data specification, only generating regions that\
            have changed and need to be reloaded

        :param spec: Where to write the regenerated spec
        :type spec: ~data_specification.DataSpecificationGenerator
        :param placement: Where are we regenerating for?
        :type placement: ~pacman.model.placements.Placement
        """

    @abstractmethod
    def requires_memory_regions_to_be_reloaded(self):
        """ Return true if any data region needs to be reloaded

        :rtype: bool
        """

    @abstractmethod
    def mark_regions_reloaded(self):
        """ Indicate that the regions have been reloaded
        """
