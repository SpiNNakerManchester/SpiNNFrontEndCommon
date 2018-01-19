import struct
import logging

from spinn_utilities.progress_bar import ProgressBar
from spinnman.messages.sdp import SDPFlag, SDPHeader, SDPMessage
from spinnman.model.enums import CPUState
from spinn_front_end_common.utilities.constants \
    import SDP_PORTS, SDP_RUNNING_MESSAGE_CODES
from spinn_front_end_common.utilities.exceptions import ConfigurationException

logger = logging.getLogger(__name__)


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

        if (len(error_cores) != 0 or len(watchdog_cores) != 0 or
                len(idle_cores) != 0):
            raise ConfigurationException(
                "Some cores have crashed. RTE cores {}, watch-dogged cores {},"
                " idle cores {}".format(
                    error_cores.values(), watchdog_cores.values(),
                    idle_cores.values()))

        # check that all cores are in the state FINISHED which shows that
        # the core has received the message and done provenance updating
        attempts = 0
        while processors_completed != total_processors and attempts < 10:
            attempts += 1
            unsuccessful_cores = txrx.get_cores_not_in_state(
                all_core_subsets, CPUState.FINISHED)

            for (x, y, p) in unsuccessful_cores.iterkeys():
                data = struct.pack(
                    "<I", SDP_RUNNING_MESSAGE_CODES.
                    SDP_UPDATE_PROVENCE_REGION_AND_EXIT.value)
                txrx.send_sdp_message(SDPMessage(SDPHeader(
                    flags=SDPFlag.REPLY_NOT_EXPECTED,
                    destination_cpu=p,
                    destination_chip_x=x,
                    destination_port=SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value,
                    destination_chip_y=y), data=data))

            processors_completed = txrx.get_core_state_count(
                app_id, CPUState.FINISHED)

            left_over_now = total_processors - processors_completed
            to_update = left_to_do_cores - left_over_now
            left_to_do_cores = left_over_now
            if to_update != 0:
                progress.update(to_update)
        if attempts >= 10:
            logger.error("Unable to Finish getting provenance data. "
                         "Abandoned after too many retries. "
                         "Board may be left in an unstable state!")

        progress.end()
