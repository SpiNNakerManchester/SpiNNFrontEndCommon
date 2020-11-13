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

from pacman.model.graphs.machine import MachineVertex
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractRewritesDataSpecification(object):
    """ Indicates an object that allows data to be changed after run,\
        and so can rewrite the data specification
    """

    __slots__ = []

    _WRONG_VERTEX_TYPE_ERROR = (
        "The vertex {} is not of type MachineVertex. By not being a "
        "machine vertex, the SpiNNFrontEndCommon function DSGRegionReloader "
        "will not check this vertex")

    def __new__(cls, *more):
        if not issubclass(cls, MachineVertex):
            raise SpinnFrontEndException(
                cls._WRONG_VERTEX_TYPE_ERROR.format(cls))
        return super(AbstractRewritesDataSpecification, cls).__new__(cls)

    @abstractmethod
    def regenerate_data_specification(self, spec, placement):
        """ Regenerate the data specification, only generating regions that\
            have changed and need to be reloaded

        :param ~data_specification.DataSpecificationGenerator spec:
            Where to write the regenerated spec
        :param ~pacman.model.placements.Placement placement:
            Where are we regenerating for?
        """

    @abstractmethod
    def reload_required(self):
        """ Return true if any data region needs to be reloaded

        :rtype: bool
        """

    @abstractmethod
    def set_reload_required(self, new_value):
        """ Indicate that the regions have been reloaded

        :param new_value: the new value
        :rtype: None
        """
