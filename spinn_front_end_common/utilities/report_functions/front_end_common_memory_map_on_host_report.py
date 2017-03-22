
import logging
import os

logger = logging.getLogger(__name__)


class FrontEndCommonMemoryMapOnHostReport(object):
    """ Report on memory usage
    """

    def __call__(
            self, report_default_directory,
            processor_to_app_data_base_address):
        """

        :param report_default_directory:
        :param processor_to_app_data_base_address:
        :rtype: None
        """

        file_name = os.path.join(report_default_directory,
                                 "memory_map_from_processor_to_address_space")
        output = None
        try:
            output = open(file_name, "w")
        except IOError:
            logger.error("Generate_placement_reports: Can't open file"
                         " {} for writing.".format(file_name))

        output.write("On host data specification executor\n")

        for key in processor_to_app_data_base_address:
            data = processor_to_app_data_base_address[key]
            output.write(
                "{}: ('start_address': {}, hex({}), 'memory_used': {}, "
                "'memory_written': {} \n".format(
                    key, data['start_address'], hex(data['start_address']),
                    data['memory_used'], data['memory_written']))

        output.flush()
        output.close()
