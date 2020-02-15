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

import logging
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from .simulator_interface import SimulatorInterface
from spinn_utilities.overrides import overrides

FAILED_STATE_MSG = "This call is only valid between setup and end/stop"

logger = FormatAdapter(logging.getLogger(__name__))


class FailedState(SimulatorInterface):
    """ Marks that the simulator has failed (and replaces said simulator).

    .. warning::
        Any method invoked on this object may fail with\
        :py:class:`~spinn_front_end_common.utilities.exceptions.ConfigurationException`.
    """

    @overrides(SimulatorInterface.add_socket_address)
    def add_socket_address(self, socket_address):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    @overrides(SimulatorInterface.buffer_manager)
    def buffer_manager(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    @overrides(SimulatorInterface.config)
    def config(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    def graph_mapper(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    @overrides(SimulatorInterface.has_ran)
    def has_ran(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    @overrides(SimulatorInterface.machine)
    def machine(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    @overrides(SimulatorInterface.machine_time_step)
    def machine_time_step(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    @overrides(SimulatorInterface.no_machine_time_steps)
    def no_machine_time_steps(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    @overrides(SimulatorInterface.placements)
    def placements(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    @overrides(SimulatorInterface.tags)
    def tags(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @overrides(SimulatorInterface.run)
    def run(self, run_time):
        raise ConfigurationException(FAILED_STATE_MSG)

    @overrides(SimulatorInterface.stop)
    def stop(self):
        logger.error("Ignoring call to stop/end as no simulator running")

    @property
    @overrides(SimulatorInterface.transceiver)
    def transceiver(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    @overrides(SimulatorInterface.time_scale_factor)
    def time_scale_factor(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    @overrides(SimulatorInterface.use_virtual_board)
    def use_virtual_board(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @overrides(SimulatorInterface.verify_not_running)
    def verify_not_running(self):
        raise ConfigurationException(FAILED_STATE_MSG)
