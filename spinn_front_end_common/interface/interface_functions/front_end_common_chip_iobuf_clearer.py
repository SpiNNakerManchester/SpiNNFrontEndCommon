from spinn_front_end_common.utilities.scp.clear_iobuf_process import \
    ClearIOBUFProcess

from spinn_front_end_common.utilities import exceptions


class FrontEndCommonChipIOBufClearer(object):
    """ Updates the runtime of an application running on a spinnaker machine
    """

    __slots__ = []

    def __call__(self, transceiver, executable_targets, ran_token):

        if not ran_token:
            raise exceptions.ConfigurationException(
                "The simulation has to have ran before running this system")

        process = ClearIOBUFProcess(transceiver._scamp_connection_selector)
        process.clear_iobuf(executable_targets.all_core_subsets,
                            len(executable_targets.all_core_subsets))
        return True
