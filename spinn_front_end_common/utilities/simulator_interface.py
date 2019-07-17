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
    AbstractBase, abstractproperty, abstractmethod)


@add_metaclass(AbstractBase)
class SimulatorInterface(object):

    __slots__ = ()

    @abstractmethod
    def add_socket_address(self, socket_address):
        pass

    @abstractproperty
    def buffer_manager(self):
        pass

    @abstractproperty
    def config(self):
        pass

    @abstractproperty
    def graph_mapper(self):
        pass

    @abstractproperty
    def has_ran(self):
        pass

    @abstractmethod
    def verify_not_running(self):
        pass

    @abstractproperty
    def increment_none_labelled_vertex_count(self):
        pass

    @abstractproperty
    def machine(self):
        pass

    @abstractproperty
    def machine_time_step(self):
        pass

    @abstractproperty
    def no_machine_time_steps(self):
        pass

    @abstractproperty
    def none_labelled_vertex_count(self):
        pass

    @abstractproperty
    def placements(self):
        pass

    @abstractproperty
    def tags(self):
        pass

    @abstractproperty
    def time_scale_factor(self):
        pass

    @abstractproperty
    def run(self, run_time):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractproperty
    def transceiver(self):
        pass

    @abstractproperty
    def use_virtual_board(self):
        pass
