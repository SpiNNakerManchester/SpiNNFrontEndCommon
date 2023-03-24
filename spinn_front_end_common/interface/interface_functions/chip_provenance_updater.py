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
from spinnman.model.enums import CPUState
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import (
    SDP_PORTS, SDP_RUNNING_MESSAGE_CODES)
from spinn_front_end_common.utilities.exceptions import ConfigurationException

logger = FormatAdapter(logging.getLogger(__name__))
_ONE_WORD = struct.Struct("<I")

_LIMIT = 10


def chip_provenance_updater(all_core_subsets):
    updater = _ChipProvenanceUpdater(all_core_subsets)
    # pylint: disable=protected-access
    updater._run()


class _ChipProvenanceUpdater(object):
    """
    Forces all cores to generate provenance data, and then exit.
    """

    __slots__ = ["__all_cores", "__app_id", "__txrx"]

    def __init__(self, all_core_subsets):
        """
        :param ~spinn_machine.CoreSubsets all_core_subsets:
        """
        self.__all_cores = all_core_subsets
        self.__app_id = FecDataView.get_app_id()
        self.__txrx = FecDataView.get_transceiver()

    def _run(self):
        # check that the right number of processors are in sync
        processors_completed = self.__txrx.get_core_state_count(
            self.__app_id, CPUState.FINISHED)
        total_processors = len(self.__all_cores)
        left_to_do_cores = total_processors - processors_completed

        progress = ProgressBar(
            left_to_do_cores,
            "Forcing error cores to generate provenance data")

        error_cores = self.__txrx.get_cores_in_state(
            self.__all_cores, CPUState.RUN_TIME_EXCEPTION)
        watchdog_cores = self.__txrx.get_cores_in_state(
            self.__all_cores, CPUState.WATCHDOG)
        idle_cores = self.__txrx.get_cores_in_state(
            self.__all_cores, CPUState.IDLE)

        if error_cores or watchdog_cores or idle_cores:
            raise ConfigurationException(
                "Some cores have crashed. "
                f"RTE cores {error_cores.values()}, "
                f"watch-dogged cores {watchdog_cores.values()}, "
                f"idle cores {idle_cores.values()}")

        # check that all cores are in the state FINISHED which shows that
        # the core has received the message and done provenance updating
        self._update_provenance(
            total_processors, processors_completed, progress)
        progress.end()

    def _update_provenance(
            self, total_processors, processors_completed, progress):
        """
        :param int total_processors:
        :param int processors_completed:
        :param ~.ProgressBar progress:
        """
        # pylint: disable=too-many-arguments
        left_to_do_cores = total_processors - processors_completed
        attempts = 0
        while processors_completed != total_processors and attempts < _LIMIT:
            attempts += 1
            unsuccessful_cores = self.__txrx.get_cores_not_in_state(
                self.__all_cores, CPUState.FINISHED)

            for (x, y, p) in unsuccessful_cores.keys():
                self._send_chip_update_provenance_and_exit(x, y, p)

            processors_completed = self.__txrx.get_core_state_count(
                self.__app_id, CPUState.FINISHED)

            left_over_now = total_processors - processors_completed
            to_update = left_to_do_cores - left_over_now
            left_to_do_cores = left_over_now
            if to_update != 0:
                progress.update(to_update)
                sleep(0.5)
        if processors_completed != total_processors:
            logger.error("Unable to Finish getting provenance data. "
                         "Abandoned after too many retries. "
                         "Board may be left in an unstable state!")

    def _send_chip_update_provenance_and_exit(self, x, y, p):
        """
        :param int x:
        :param int y:
        :param int p:
        """
        cmd = SDP_RUNNING_MESSAGE_CODES.SDP_UPDATE_PROVENCE_REGION_AND_EXIT
        port = SDP_PORTS.RUNNING_COMMAND_SDP_PORT

        self.__txrx.send_sdp_message(SDPMessage(
            SDPHeader(
                flags=SDPFlag.REPLY_NOT_EXPECTED,
                destination_port=port.value, destination_cpu=p,
                destination_chip_x=x, destination_chip_y=y),
            data=_ONE_WORD.pack(cmd.value)))
