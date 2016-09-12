from spinnman.model.cpu_state import CPUState

from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.abstract_models\
    .abstract_binary_uses_simulation_run import AbstractBinaryUsesSimulationRun
from spinn_front_end_common.utilities.scp.update_runtime_process \
    import UpdateRuntimeProcess


class FrontEndCommonChipRuntimeUpdater(object):
    """ Updates the runtime of an application running on a spinnaker machine
    """

    __slots__ = []

    def __call__(
            self, txrx, no_sync_changes, app_id, placements,
            executable_targets, no_machine_timesteps, loaded_binaries_token,
            graph_mapper=None):

        if not loaded_binaries_token:
            raise exceptions.ConfigurationException(
                "The binaries must be loaded before the run time updater is"
                " called")

        # Find placements whose run time can be updated
        updatable_binaries, _ = helpful_functions.get_executables_by_run_type(
            executable_targets, placements, graph_mapper,
            AbstractBinaryUsesSimulationRun)

        if updatable_binaries.total_processors > 0:
            helpful_functions.wait_for_cores_to_be_ready(
                updatable_binaries, app_id, txrx, CPUState.PAUSED)

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
