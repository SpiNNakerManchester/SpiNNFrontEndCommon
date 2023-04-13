# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.data import FecDataView


def load_fixed_routes():
    """
    Load a set of fixed routes onto a SpiNNaker machine.

    :param ~spinnman.transceiver.Transceiver transceiver:
    """
    fixed_routes = FecDataView.get_fixed_routes()
    progress_bar = ProgressBar(
        total_number_of_things_to_do=len(fixed_routes),
        string_describing_what_being_progressed="loading fixed routes")
    app_id = FecDataView.get_app_id()
    transceiver = FecDataView.get_transceiver()
    for chip_x, chip_y in progress_bar.over(fixed_routes.keys()):
        transceiver.load_fixed_route(
            chip_x, chip_y, fixed_routes[chip_x, chip_y], app_id)
