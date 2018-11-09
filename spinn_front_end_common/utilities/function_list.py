import os
from spinn_front_end_common.interface import interface_functions
from spinn_front_end_common.utilities import report_functions
from spinn_front_end_common import mapping_algorithms


def get_front_end_common_pacman_xml_paths():
    """ Get the XML path for the front end common interface functions
    """
    return [
        os.path.join(
            os.path.dirname(interface_functions.__file__),
            "front_end_common_interface_functions.xml"),
        os.path.join(
            os.path.dirname(report_functions.__file__),
            "front_end_common_reports.xml"),
        os.path.join(
            os.path.dirname(mapping_algorithms.__file__),
            "front_end_common_mapping_algorithms.xml"
        )
    ]
