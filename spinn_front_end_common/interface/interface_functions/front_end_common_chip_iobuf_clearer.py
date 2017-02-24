from spinn_front_end_common.utilities.scp.clear_iobuf_process import \
    ClearIOBUFProcess
from spinn_front_end_common.abstract_models\
    .abstract_binary_uses_simulation_run import AbstractBinaryUsesSimulationRun

from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities import helpful_functions


class FrontEndCommonChipIOBufClearer(object):
    """ Updates the runtime of an application running on a spinnaker machine
    """

    __slots__ = []

    def __call__(
            self, transceiver, executable_targets, ran_token, placements,
            graph_mapper=None):

        if not ran_token:
            raise exceptions.ConfigurationException(
                "The simulation has to have ran before running this system")

        clearable_targets, _ = helpful_functions.get_executables_by_run_type(
            executable_targets, placements, graph_mapper,
            AbstractBinaryUsesSimulationRun)

        process = ClearIOBUFProcess(transceiver._scamp_connection_selector)
        process.clear_iobuf(clearable_targets.all_core_subsets,
                            len(clearable_targets.all_core_subsets))
        return True
