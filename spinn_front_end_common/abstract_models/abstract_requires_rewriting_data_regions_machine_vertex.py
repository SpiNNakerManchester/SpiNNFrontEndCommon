from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractRequiresRewriteDataRegionsMachineVertex(object):
    """ interface for rewriting dsg regions in between calls to run for a
    machine vertex
    """

    @abstractmethod
    def regions_and_data_spec_to_rewrite(
            self, placement, hostname, report_directory, write_text_specs,
            reload_application_data_file_path):
        """ method for getting regions that need to be rewritten between runs
        :param placement: placement object for the vertex being dealt with
        :param hostname: the machine name
        :param report_directory: the location where reports are going to be
        stored
        :param write_text_specs: bool that controls in the human readable
        dsg files are created
        :param reload_application_data_file_path: the folder where reloaded
        dsg data will be placed
        :return: a dict of data regions and filepaths
        """

    @abstractmethod
    def requires_memory_regions_to_be_reloaded(self):
        """ allows a flag check on if this functionality will be needed

        :return: bool which is true if it requires memory regions to be
        reloaded
        """

    @abstractmethod
    def mark_regions_reloaded(self):
        """ allows the flag that the dsg regions have been reloaded to be
        cleared

        :return: None
        """
