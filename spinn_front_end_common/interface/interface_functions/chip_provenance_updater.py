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

import struct
import logging
from six import iterkeys
from spinn_utilities.progress_bar import ProgressBar
from spinnman.messages.sdp import SDPFlag, SDPHeader, SDPMessage
from spinnman.model.enums import CPUState
from spinn_front_end_common.utilities.constants import (
    SDP_PORTS, SDP_RUNNING_MESSAGE_CODES)
from spinn_front_end_common.utilities.exceptions import ConfigurationException

logger = logging.getLogger(__name__)
_ONE_WORD = struct.Struct("<I")

_LIMIT = 10


class ChipProvenanceUpdater(object):
    """ Forces all cores to generate provenance data, and then exit
    """

    __slots__ = []

    def __call__(self, txrx, app_id, all_core_subsets):
        # check that the right number of processors are in sync
        processors_completed = txrx.get_core_state_count(
            app_id, CPUState.FINISHED)
        total_processors = len(all_core_subsets)
        left_to_do_cores = total_processors - processors_completed

        progress = ProgressBar(
            left_to_do_cores,
            "Forcing error cores to generate provenance data")

        error_cores = txrx.get_cores_in_state(
            all_core_subsets, CPUState.RUN_TIME_EXCEPTION)
        watchdog_cores = txrx.get_cores_in_state(
            all_core_subsets, CPUState.WATCHDOG)
        idle_cores = txrx.get_cores_in_state(
            all_core_subsets, CPUState.IDLE)

        if error_cores or watchdog_cores or idle_cores:
            raise ConfigurationException(
                "Some cores have crashed. RTE cores {}, watch-dogged cores {},"
                " idle cores {}".format(
                    error_cores.values(), watchdog_cores.values(),
                    idle_cores.values()))

        # check that all cores are in the state FINISHED which shows that
        # the core has received the message and done provenance updating
        self._update_provenance(txrx, total_processors, processors_completed,
                                all_core_subsets, app_id, progress)
        progress.end()

    def _update_provenance(self, txrx, total_processors, processors_completed,
                           all_core_subsets, app_id, progress):
        # pylint: disable=too-many-arguments
        left_to_do_cores = total_processors - processors_completed
        attempts = 0
        while processors_completed != total_processors and attempts < _LIMIT:
            attempts += 1
            unsuccessful_cores = txrx.get_cores_not_in_state(
                all_core_subsets, CPUState.FINISHED)

            for (x, y, p) in iterkeys(unsuccessful_cores):
                self._send_chip_update_provenance_and_exit(txrx, x, y, p)

            processors_completed = txrx.get_core_state_count(
                app_id, CPUState.FINISHED)

            left_over_now = total_processors - processors_completed
            to_update = left_to_do_cores - left_over_now
            left_to_do_cores = left_over_now
            if to_update != 0:
                progress.update(to_update)
        if processors_completed != total_processors:
            logger.error("Unable to Finish getting provenance data. "
                         "Abandoned after too many retries. "
                         "Board may be left in an unstable state!")

    @staticmethod
    def _send_chip_update_provenance_and_exit(txrx, x, y, p):
        cmd = SDP_RUNNING_MESSAGE_CODES.SDP_UPDATE_PROVENCE_REGION_AND_EXIT
        port = SDP_PORTS.RUNNING_COMMAND_SDP_PORT

        txrx.send_sdp_message(SDPMessage(
            SDPHeader(
                flags=SDPFlag.REPLY_NOT_EXPECTED,
                destination_port=port.value, destination_cpu=p,
                destination_chip_x=x, destination_chip_y=y),
            data=_ONE_WORD.pack(cmd.value)))
