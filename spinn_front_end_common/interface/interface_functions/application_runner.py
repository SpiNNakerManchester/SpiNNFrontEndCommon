import logging
import time

from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.utility_objs import ExecutableStartType
from spinn_machine import CoreSubsets

from spinnman.messages.scp.enums import Signal
from spinnman.model.enums import CPUState

logger = logging.getLogger(__name__)


class ApplicationRunner(object):
    """ Ensures all cores are initialised correctly, ran, and completed\
        successfully.
    """

    __slots__ = []

    def __call__(
            self, buffer_manager, wait_on_confirmation, send_stop_notification,
            send_start_notification, notification_interface,
            executable_targets, executable_start_types, app_id, txrx, runtime,
            time_scale_factor, loaded_reverse_iptags_token,
            loaded_iptags_token, loaded_routing_tables_token,
            loaded_binaries_token, loaded_application_data_token,
            no_sync_changes, time_threshold, placements,
            run_until_complete=False):

        # check all tokens are valid
        if (not loaded_reverse_iptags_token or not loaded_iptags_token or
                not loaded_routing_tables_token or not loaded_binaries_token or
                not loaded_application_data_token):
            raise ConfigurationException(
                "Not all valid tokens have been given in the positive state")

        logger.info("*** Running simulation... *** ")

        # Get the expected state of the application, depending on the run type
        expected_start_states, core_subsets_by_executable, sync_signal, \
            expected_end_states, no_sync_changes = \
            self._determine_start_states(
                executable_start_types, no_sync_changes, placements)

        # wait for all cores to be ready
        for executable_start_type in expected_start_states.keys():
            txrx.wait_for_cores_to_be_in_state(
                core_subsets_by_executable[executable_start_type], app_id,
                expected_start_states[executable_start_type])

        # set the buffer manager into a resume state, so that if it had ran
        # before it'll work again
        buffer_manager.resume()

        # every thing is in sync0 so load the initial buffers
        buffer_manager.load_initial_buffers()

        # wait till external app is ready for us to start if required
        if notification_interface is not None and wait_on_confirmation:
            notification_interface.wait_for_confirmation()

        # set off the executables that are in sync state \
        # (sending to all is just as safe)
        if sync_signal is not None:
            txrx.send_signal(app_id, sync_signal)
            txrx.wait_for_cores_to_be_in_state(
                executable_targets.all_core_subsets, app_id,
                [CPUState.RUNNING, CPUState.PAUSED, CPUState.FINISHED])

        # Send start notification
        if notification_interface is not None and send_start_notification:
            notification_interface.send_start_resume_notification()

        # Wait for the application to finish
        if runtime is None and not run_until_complete:
            logger.info("Application is set to run forever - exiting")
        else:
            timeout = None
            if not run_until_complete:
                time_to_wait = ((runtime * time_scale_factor) / 1000.0) + 0.1
                logger.info(
                    "Application started - waiting {} seconds for it to stop"
                    .format(time_to_wait))
                time.sleep(time_to_wait)
                timeout = time_threshold
            else:
                logger.info(
                    "Application started - waiting until finished")

            for executable_end_type in expected_end_states.keys():
                txrx.wait_for_cores_to_be_in_state(
                    core_subsets_by_executable[executable_end_type], app_id,
                    expected_end_states[executable_end_type], timeout=timeout)

        if (notification_interface is not None and
                send_stop_notification and runtime is not None):
            notification_interface.send_stop_pause_notification()

        return True, no_sync_changes

    def _determine_start_states(
            self, executable_start_types, no_sync_changes, placements):
        """ sorts out start states, and creates core subsets of the states for
        further checks.
        
        :param executable_start_types: the dict of start type to vertices
        :param no_sync_changes: sync counter
        :param placements: placements
        :return: list of expected states, the core subsets for each\
         executable type, and the sync signal
        """
        expected_start_states = dict()
        expected_end_states = dict()
        core_subsets = dict()
        sync_signal = None
        for executable_start_type in executable_start_types.keys():

            # cores that ignore all control and are just running
            if executable_start_type == ExecutableStartType.RUNNING:
                expected_start_states[executable_start_type] = [
                    CPUState.RUNNING, CPUState.FINISHED, CPUState.PAUSED,
                    CPUState.SYNC0, CPUState.SYNC1
                ]
                expected_end_states[executable_start_type] = [CPUState.RUNNING]

            # cores that require a sync barrier
            elif executable_start_type == ExecutableStartType.SYNC:
                sync_signal = Signal.SYNC0
                expected_start_states[executable_start_type] = [CPUState.SYNC0]
                expected_end_states[executable_start_type] = \
                    [CPUState.FINISHED]

            # cores that use our sim interface
            elif (executable_start_type ==
                    ExecutableStartType.USES_SIMULATION_INTERFACE):
                if no_sync_changes % 2 == 0:
                    expected_start_states[executable_start_type] = \
                        [CPUState.SYNC0, CPUState.PAUSED]
                    sync_signal = Signal.SYNC0
                else:
                    expected_start_states[executable_start_type] = \
                        [CPUState.SYNC1, CPUState.PAUSED]
                    sync_signal = Signal.SYNC1

                # when it falls out of the running, it'll be in a next sync \
                # state, thus update needed
                no_sync_changes += 1
                expected_end_states[executable_start_type] = [CPUState.PAUSED]

            # determine core subset
            core_subsets[executable_start_type] = \
                self._convert_to_core_subsets(
                    executable_start_types[executable_start_type],
                    placements)

        if len(expected_start_states) == 0:
            raise ConfigurationException(
                "Unknown executable start types {}".format(
                    executable_start_types))
        return expected_start_states, core_subsets, sync_signal, \
               expected_end_states, no_sync_changes

    @staticmethod
    def _convert_to_core_subsets(vertices, placements):
        core_subsets = CoreSubsets()
        for vertex in vertices:
            vertex_placement = placements.get_placement_of_vertex(vertex)
            core_subsets.add_processor(
                x=vertex_placement.x, y=vertex_placement.y,
                processor_id=vertex_placement.p)
        return core_subsets
