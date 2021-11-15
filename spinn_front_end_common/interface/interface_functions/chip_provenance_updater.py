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
from time import sleep
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from spinnman.messages.sdp import SDPFlag, SDPHeader, SDPMessage
from spinnman.model.enums import CPUState
from spinn_front_end_common.utilities.constants import (
    SDP_PORTS, SDP_RUNNING_MESSAGE_CODES)
from spinn_front_end_common.utilities.exceptions import ConfigurationException

logger = FormatAdapter(logging.getLogger(__name__))
_ONE_WORD = struct.Struct("<I")

_LIMIT = 10


def chip_provenance_updater(txrx, app_id, all_core_subsets):
    updater = _ChipProvenanceUpdater(txrx, app_id, all_core_subsets)
    updater._run()


class _ChipProvenanceUpdater(object):
    """ Forces all cores to generate provenance data, and then exit.
    """

    __slots__ = ["__all_cores", "__app_id", "__txrx"]

    def __init__(self, txrx, app_id, all_core_subsets):
        """
        :param ~spinnman.transceiver.Transceiver txrx:
        :param int app_id:
        :param ~spinn_machine.CoreSubsets all_core_subsets:
        """
        self.__all_cores = all_core_subsets
        self.__app_id = app_id
        self.__txrx = txrx

    def _run(self):
        # check that the right number of processors are in sync
        processors_completed = self.__txrx.get_core_state_count(
            self.__app_id, CPUState.FINISHED)
        total_processors = len(self.__all_core_subsets)
        left_to_do_cores = total_processors - processors_completed

        progress = ProgressBar(
            left_to_do_cores,
            "Forcing error cores to generate provenance data")

        error_cores = self.__txrx.get_cores_in_state(
            self.__all_core_subsets, CPUState.RUN_TIME_EXCEPTION)
        watchdog_cores = self.__.get_cores_in_state(
            self.__all_core_subsets, CPUState.WATCHDOG)
        idle_cores = self.__txrx.get_cores_in_state(
            self.__all_core_subsets, CPUState.IDLE)

        if error_cores or watchdog_cores or idle_cores:
            raise ConfigurationException(
                "Some cores have crashed. RTE cores {}, watch-dogged cores {},"
                " idle cores {}".format(
                    error_cores.values(), watchdog_cores.values(),
                    idle_cores.values()))

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
