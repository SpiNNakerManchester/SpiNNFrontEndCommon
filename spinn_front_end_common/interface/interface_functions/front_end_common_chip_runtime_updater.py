from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities.scp.update_runtime_process \
    import UpdateRuntimeProcess


class FrontEndCommonChipRuntimeUpdater(object):
    """ Updates the runtime of an application running on a spinnaker machine
    """

    def __call__(
            self, txrx, no_sync_changes, app_id,
            executable_targets, no_machine_timesteps, loaded_binaries_token):

        if not loaded_binaries_token:
            raise exceptions.ConfigurationException(
                "The binaries must be loaded before the run time updater is"
                " called")

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

        return {'no_sync_changes': no_sync_changes}
