from spinnman.model.enums import CPUState
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.scp import UpdateRuntimeProcess


class ChipRuntimeUpdater(object):
    """ Updates the runtime of an application running on a SpiNNaker machine.
    """

    __slots__ = []

    def __call__(
            self, txrx, app_id, executable_types, no_machine_timesteps):

        core_subsets = \
            executable_types[ExecutableType.USES_SIMULATION_INTERFACE]

        txrx.wait_for_cores_to_be_in_state(
            core_subsets, app_id, [CPUState.PAUSED, CPUState.READY])

        infinite_run = 0
        if no_machine_timesteps is None:
            infinite_run = 1
            no_machine_timesteps = 0

        # TODO: Expose the connection selector in SpiNNMan
        process = UpdateRuntimeProcess(txrx.scamp_connection_selector)
        process.update_runtime(
            no_machine_timesteps, infinite_run, core_subsets,
            len(core_subsets))
