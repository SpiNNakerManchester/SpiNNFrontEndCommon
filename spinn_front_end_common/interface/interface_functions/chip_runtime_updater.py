from spinn_front_end_common.utilities.exceptions import ConfigurationException

from spinnman.model.enums import CPUState
from spinn_front_end_common.utilities.scp import UpdateRuntimeProcess


class ChipRuntimeUpdater(object):
    """ Updates the runtime of an application running on a spinnaker machine
    """

    __slots__ = []

    def __call__(
            self, txrx, app_id, executable_targets,
            no_machine_timesteps, loaded_binaries_token):
        if not loaded_binaries_token:
            raise ConfigurationException(
                "The binaries must be loaded before the run time updater is"
                " called")

        txrx.wait_for_cores_to_be_in_state(
            executable_targets.all_core_subsets, app_id, [CPUState.PAUSED])

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

        return True
