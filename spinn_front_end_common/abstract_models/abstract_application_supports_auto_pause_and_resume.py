# Copyright (c) 2019-2020 The University of Manchester
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

from spinn_utilities.abstract_base import abstractmethod, AbstractBase
from six import add_metaclass


@add_metaclass(AbstractBase)
class AbstractApplicationSupportsAutoPauseAndResume(object):

    @abstractmethod
    def my_variable_local_time_period(
            self, default_machine_time_step, variable):
        """ allows an application vertex to define a time step per recorded /
        variable

        :param default_machine_time_step: the simulator time step
        :param variable: the variable to ask about time step for
        :return: the time period (machine time step) for this machine vertex
        """
