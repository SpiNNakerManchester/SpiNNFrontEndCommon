from spinn_front_end_common.utilities.scp import ClearIOBUFProcess


class ChipIOBufClearer(object):
    """ Updates the runtime of an application running on a spinnaker machine
    """

    __slots__ = []

    def __call__(self, transceiver, executable_targets):

        process = ClearIOBUFProcess(transceiver._scamp_connection_selector)
        process.clear_iobuf(executable_targets.all_core_subsets,
                            len(executable_targets.all_core_subsets))
