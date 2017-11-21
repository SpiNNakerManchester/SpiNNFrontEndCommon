from spinn_front_end_common.utilities.scp import ClearIOBUFProcess

from spinn_front_end_common.utilities.utility_objs import ExecutableType


class ChipIOBufClearer(object):
    """ Updates the runtime of an application running on a spinnaker machine
    """

    __slots__ = []

    def __call__(self, transceiver, executable_types):

        core_subsets = \
            executable_types[ExecutableType.USES_SIMULATION_INTERFACE]

        process = ClearIOBUFProcess(transceiver.scamp_connection_selector)
        process.clear_iobuf(core_subsets, len(core_subsets))
