from pacman.utilities.utility_objs.progress_bar import ProgressBar
from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.model.cpu_state import CPUState
from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions
import struct


class FrontEndCommonRuntimeUpdater(object):
    """ Updates the runtime of an application running on a spinnaker machine
    """

    def __call__(
            self, placements, txrx, no_sync_changes, app_id,
            executable_targets, no_machine_timesteps, loaded_binaries_token):

        progress_bar = ProgressBar(2, "Updating on chip's runtime")

        if not loaded_binaries_token:
            raise exceptions.ConfigurationException(
                "The run time token is set to false, and therefore the runtime"
                "updater cannot be ran yet.")

        # check that the right number of processors are in sync0
        processors_ready = \
            txrx.get_core_state_count(app_id, CPUState.CPU_STATE_12)
        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

        # check that all cores are in the state CPU_STATE_12 which shows that
        # the core has received the new runtime
        while processors_ready != total_processors:
            unsuccessful_cores = helpful_functions.get_cores_not_in_state(
                all_core_subsets, CPUState.CPU_STATE_12, txrx)

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

            processors_ready = txrx.get_core_state_count(
                app_id, CPUState.CPU_STATE_12)
        progress_bar.update()

        # reset the state to the old state so that it can be used by the
        # application runner code
        if no_sync_changes % 2 == 0:
            sync_state = CPUState.SYNC0
        else:
            sync_state = CPUState.SYNC1
        processors_ready = txrx.get_core_state_count(app_id, sync_state)

        # check that all cores are in the state CPU_STATE_12 which shows that
        # the core has received the new runtime
        while processors_ready != total_processors:
            unsuccessful_cores = helpful_functions.get_cores_not_in_state(
                all_core_subsets, sync_state, txrx)

            for (x, y, p) in unsuccessful_cores:
                data = struct.pack(
                    "<II",
                    constants.SDP_RUNNING_MESSAGE_CODES.SDP_SWITCH_STATE.value,
                    sync_state.value)
                txrx.send_sdp_message(SDPMessage(SDPHeader(
                    flags=SDPFlag.REPLY_NOT_EXPECTED,
                    destination_cpu=p,
                    destination_chip_x=x,
                    destination_port=(
                        constants.SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value),
                    destination_chip_y=y), data=data))

            processors_ready = txrx.get_core_state_count(app_id, sync_state)
        progress_bar.update()
        progress_bar.end()

        return {'no_sync_changes': no_sync_changes}
