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

from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.data import FecDataView


def load_fixed_routes(fixed_routes):
    """ Load a set of fixed routes onto a SpiNNaker machine.

    :param fixed_routes:
    :type fixed_routes:
        dict(tuple(int,int),~spinn_machine.FixedRouteEntry)
    :param ~spinnman.transceiver.Transceiver transceiver:
    """
    progress_bar = ProgressBar(
        total_number_of_things_to_do=len(fixed_routes),
        string_describing_what_being_progressed="loading fixed routes")
    view = FecDataView()
    app_id = view.app_id
    transceiver = view.transceiver
    for chip_x, chip_y in progress_bar.over(fixed_routes.keys()):
        transceiver.load_fixed_route(
            chip_x, chip_y, fixed_routes[chip_x, chip_y], app_id)
