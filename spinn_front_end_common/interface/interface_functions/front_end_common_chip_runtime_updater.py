from spinn_front_end_common.utilities import exceptions

from spinnman.model.enums.cpu_state import CPUState
from spinn_front_end_common.utilities.scp.update_runtime_process \
    import UpdateRuntimeProcess
from spinnman.model.enums.executable_start_type import ExecutableStartType


class FrontEndCommonChipRuntimeUpdater(object):
    """ Updates the runtime of an application running on a spinnaker machine
    """

    __slots__ = []

    def __call__(
            self, txrx, no_sync_changes, app_id, executable_targets,
            no_machine_timesteps, loaded_binaries_token):

        if not loaded_binaries_token:
            raise exceptions.ConfigurationException(
                "The binaries must be loaded before the run time updater is"
                " called")

        # Find placements whose run time can be updated
        updatable_binaries = executable_targets.get_start_core_subsets(
            ExecutableStartType.USES_SIMULATION_INTERFACE)

        if len(updatable_binaries) > 0:
            txrx.wait_for_cores_to_be_ready(
                updatable_binaries, app_id, [CPUState.PAUSED])

            infinite_run = 0
            if no_machine_timesteps is None:
                infinite_run = 1
                no_machine_timesteps = 0

            # TODO: Expose the connection selector in SpiNNMan
            process = UpdateRuntimeProcess(txrx._scamp_connection_selector)
            process.update_runtime(
                no_machine_timesteps, infinite_run,
                executable_targets.all_core_subsets,
                executable_targets.total_processors)

        return no_sync_changes, True
