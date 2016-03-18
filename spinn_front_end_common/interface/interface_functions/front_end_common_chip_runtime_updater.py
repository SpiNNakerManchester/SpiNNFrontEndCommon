from spinn_machine.utilities.progress_bar import ProgressBar

from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.model.cpu_state import CPUState
from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions

import struct


class FrontEndCommonChipRuntimeUpdater(object):
    """ Updates the runtime of an application running on a spinnaker machine
    """

    def __call__(
            self, txrx, no_sync_changes, app_id,
            executable_targets, no_machine_timesteps, loaded_binaries_token):

        progress_bar = ProgressBar(
            executable_targets.total_processors, "Updating run time")

        if not loaded_binaries_token:
            raise exceptions.ConfigurationException(
                "The binaries must be loaded before the run time updater is"
                " called")

        # Work out the sync state to expect
        if no_sync_changes % 2 == 0:
            sync_state = CPUState.SYNC0
        else:
            sync_state = CPUState.SYNC1

        # check that the right number of processors are paused
        processors_ready = txrx.get_core_state_count(app_id, sync_state)
        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets
        progress_bar.update(processors_ready)
        last_n_ready = processors_ready

        # check that all cores are in the sync state which shows that
        # the core has received the new runtime
        while processors_ready != total_processors:
            unsuccessful_cores = helpful_functions.get_cores_not_in_state(
                all_core_subsets, sync_state, txrx)

            if len(unsuccessful_cores) == 0:
                progress_bar.update(total_processors - last_n_ready)
                break

            for (x, y, p) in unsuccessful_cores:
                infinite_run = 0
                if no_machine_timesteps is None:
                    infinite_run = 1
                    no_machine_timesteps = 0

                data = struct.pack(
                    "<III",
                    (constants.SDP_RUNNING_MESSAGE_CODES
                     .SDP_NEW_RUNTIME_ID_CODE.value),
                    no_machine_timesteps, infinite_run)
                txrx.send_sdp_message(SDPMessage(SDPHeader(
                    flags=SDPFlag.REPLY_NOT_EXPECTED,
                    destination_cpu=p,
                    destination_chip_x=x,
                    destination_port=(
                        constants.SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value),
                    destination_chip_y=y), data=data))

            processors_ready = txrx.get_core_state_count(app_id, sync_state)
            progress_bar.update(processors_ready - last_n_ready)
            last_n_ready = processors_ready

            # check for cores that have rte'ed or watch-dogged.
            self._check_for_bad_cores(app_id, txrx, all_core_subsets)

        progress_bar.end()

        return {'no_sync_changes': no_sync_changes}

    @staticmethod
    def _check_for_bad_cores(app_id, txrx, all_core_subsets):
        """ Locates cores that have gone into an error state

        :param app_id: the app_id to look for bad cores in
        :param txrx: the transceiver
        :param all_core_subsets: all cores in this application
        :return: None
        :raises: ExecutableFailedToStartException: if there are failed cores
        """
        # check that cores are not in unstable states already
        bad_processor_count = txrx.get_core_state_count(
            app_id, CPUState.RUN_TIME_EXCEPTION)
        bad_processor_count += txrx.get_core_state_count(
            app_id, CPUState.WATCHDOG)
        if bad_processor_count != 0:
            bad_processors = helpful_functions.get_cores_in_state(
                all_core_subsets,
                {CPUState.RUN_TIME_EXCEPTION, CPUState.WATCHDOG},
                txrx)
            error_string = helpful_functions.get_core_status_string(
                bad_processors)
            raise exceptions.ExecutableFailedToStartException(
                "{} cores were in invalid states before getting runtime set"
                " up: {}".format(bad_processor_count, error_string),
                helpful_functions.get_core_subsets(bad_processors))
