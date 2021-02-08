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

from spinn_front_end_common.utilities.globals_variables import get_simulator


class FinaliseTimingData(object):
    """ Produces the timing information for the run.
    """

    __slots__ = []

    def __call__(self):
        """
        :return:
            mapping_time, dsg_time, load_time, execute_time, extraction_time
        :rtype: tuple(float, float, float, float, float)
        """
        # Note that this algorithm "knows" the simulator is an
        # AbstractSpinnakerBase instance of some kind, and that that the
        # _end_of_run_timing method exists.
        return get_simulator()._end_of_run_timing()
