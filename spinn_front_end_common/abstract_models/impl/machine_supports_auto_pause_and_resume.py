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

from spinn_front_end_common.abstract_models.\
    abstract_machine_supports_auto_pause_and_resume import \
    AbstractMachineSupportsAutoPauseAndResume
from spinn_utilities.overrides import overrides


class MachineSupportsAutoPauseAndResume(
        AbstractMachineSupportsAutoPauseAndResume):

    @overrides(AbstractMachineSupportsAutoPauseAndResume.my_local_time_period)
    def my_local_time_period(self, simulator_time_step):
        return simulator_time_step
