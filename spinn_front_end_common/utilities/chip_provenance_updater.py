# Copyright (c) 2016 The University of Manchester
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

import struct
import logging
from time import sleep
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from spinnman.messages.sdp import SDPFlag, SDPHeader, SDPMessage
from spinnman.model.enums import (
    CPUState, SDP_PORTS, SDP_RUNNING_MESSAGE_CODES)
from spinn_front_end_common.data import FecDataView


logger = FormatAdapter(logging.getLogger(__name__))
_ONE_WORD = struct.Struct("<I")


def chip_provenance_updater(all_core_subsets, limit=10):
    """ Update the provenance on all_core_subsets

    :param ~spinn_machine.CoreSubsets all_core_subsets:
    :param int limit: How many times to try to update provenance
    """
    app_id = FecDataView.get_app_id()
    txrx = FecDataView.get_transceiver()
    n_running_cores = txrx.get_core_state_count(app_id, CPUState.RUNNING)

    progress = ProgressBar(
        n_running_cores,
        "Forcing error cores to generate provenance data")
    attempts = 0
    while n_running_cores and attempts < limit:
        attempts += 1
        running_cores = txrx.get_cpu_infos(
            all_core_subsets, CPUState.RUNNING, include=True)

        for (c_x, c_y, proc) in running_cores.keys():
            send_chip_update_provenance_and_exit(txrx, c_x, c_y, proc)
        sleep(0.5)

        n_running_cores_now = txrx.get_core_state_count(
            app_id, CPUState.RUNNING)

        to_update = n_running_cores - n_running_cores_now
        if to_update != 0:
            progress.update(to_update)
        n_running_cores = n_running_cores_now

    progress.end()
    if n_running_cores > 0:
        logger.error("Unable to Finish getting provenance data. "
                     "Abandoned after too many retries. "
                     "Board may be left in an unstable state!")


def send_chip_update_provenance_and_exit(txrx, c_x, c_y, proc):
    """
    :param int c_x:
    :param int c_y:
    :param int proc:
    """
    cmd = SDP_RUNNING_MESSAGE_CODES.SDP_UPDATE_PROVENCE_REGION_AND_EXIT
    port = SDP_PORTS.RUNNING_COMMAND_SDP_PORT

    txrx.send_sdp_message(SDPMessage(
        SDPHeader(
            flags=SDPFlag.REPLY_NOT_EXPECTED,
            destination_port=port.value, destination_cpu=proc,
            destination_chip_x=c_x, destination_chip_y=c_y),
        data=_ONE_WORD.pack(cmd.value)))
