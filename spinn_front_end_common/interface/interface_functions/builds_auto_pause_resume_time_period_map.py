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

import math

from spinn_front_end_common.abstract_models.\
    abstract_machine_supports_auto_pause_and_resume import \
    AbstractMachineSupportsAutoPauseAndResume
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar

logger = FormatAdapter(logging.getLogger(__name__))


class BuildsAutoPauseResumeTimePeriodMap(object):
    """ Extracts data in between runs
    """

    __slots__ = []

    def __call__(self, machine_graph, default_machine_time_step):

        # Read back the regions
        progress = ProgressBar(
            len(machine_graph.vertices), "collating vertices time periods")
        timer_period_map = dict()

        for vertex in progress.over(machine_graph.vertices):
            if isinstance(vertex, AbstractMachineSupportsAutoPauseAndResume):
                timer_period_map[vertex] = \
                    math.floor(vertex.my_local_time_period(
                        default_machine_time_step))
            else:
                timer_period_map[vertex] = default_machine_time_step
        return timer_period_map
