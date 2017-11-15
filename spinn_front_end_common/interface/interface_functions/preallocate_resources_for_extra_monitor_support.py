from pacman.model.resources import CoreResource, \
    PreAllocatedResourceContainer
from spinn_utilities.progress_bar import ProgressBar


class PreAllocateResourcesForExtraMonitorSupport(object):
    """ allocate resources needed for the extra monitor support
    """

    def __call__(
            self, machine, pre_allocated_resources=None,
            n_cores_to_allocate=1):
        """ setter offer

        :param machine: spinnaker machine object
        :param pre_allocated_resources: resources already pre allocated
        :param n_cores_to_allocate: config params for how many gatherers to use
        """

        progress = ProgressBar(
            len(list(machine.chips)),
            "Pre allocating resources for Extra Monitor support vertices")

        sdrams = list()
        cores = list()
        tags = list()

        # add resource requirements for re-injector and reader for data
        # extractor
        self._handle_second_monitor_support(cores, machine, progress)

        # create pre allocated resource container
        extra_monitor_pre_allocations = PreAllocatedResourceContainer(
            specific_sdram_usage=sdrams, core_resources=cores,
            specific_iptag_resources=tags)

        # add other pre allocated resources
        if pre_allocated_resources is not None:
            extra_monitor_pre_allocations.extend(pre_allocated_resources)

        # return pre allocated resources
        return extra_monitor_pre_allocations

    @staticmethod
    def _handle_second_monitor_support(cores, machine, progress):
        """ adds the second monitor pre allocations, which reflect the \
        re-injector and data extractor support

        :param cores: the storage of core requirements
        :param machine: the spinnMachine instance
        :param progress: the progress bar to operate one
        :rtype: None
        """
        for chip in progress.over(list(machine.chips)):
            cores.append(CoreResource(chip=chip, n_cores=1))
