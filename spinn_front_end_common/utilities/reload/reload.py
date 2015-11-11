"""
reload script for loading onto a amchien wtihout going through the mapper
"""
from spinn_front_end_common.utilities import helpful_functions


class Reload(object):
    """ Reload functions for reload scripts
    """

    def __init__(self, machine_name, version, reports_states, bmp_details,
                 down_chips, down_cores, number_of_boards, height, width,
                 auto_detect_bmp, enable_reinjection, xml_paths, app_id=30):

        pacman_inputs = self._create_pacman_inputs(
            machine_name, version, reports_states, bmp_details,
            down_chips, down_cores, number_of_boards, height, width,
            auto_detect_bmp, enable_reinjection, app_id)
        pacman_outputs = self._create_pacman_outputs()

        # get the list of algorithms expected to be used
        pacman_algorithms = self.create_list_of_algorithms()

        # run the pacman executor
        helpful_functions.do_mapping(
            pacman_inputs, pacman_algorithms, pacman_outputs, xml_paths,
            False)

    @staticmethod
    def _create_pacman_inputs(
            machine_name, version, reports_states, bmp_details,
            down_chips, down_cores, number_of_boards, height, width,
            auto_detect_bmp, enable_reinjection, app_id):
        """

        :param machine_name:
        :param version:
        :param reports_states:
        :param bmp_details:
        :param down_chips:
        :param down_cores:
        :param number_of_boards:
        :param height:
        :param width:
        :param auto_detect_bmp:
        :param enable_reinjection:
        :param app_id:
        :return:
        """
        inputs = list()
        inputs.append({'type': "ReportStates", 'value': reports_states})
        inputs.append({'type': 'IPAddress', 'value': machine_name})
        inputs.append({'type': "BoardVersion", 'value': version})
        inputs.append({'type': "BMPDetails", 'value': bmp_details})
        inputs.append({'type': "DownedChipsDetails", 'value': down_chips})
        inputs.append({'type': "DownedCoresDetails", 'value': down_cores})
        inputs.append({'type': "NumberOfBoards", 'value': number_of_boards})
        inputs.append({'type': "MachineWidth", 'value': width})
        inputs.append({'type': "MachineHeight", 'value': height})
        inputs.append({'type': "APPID", 'value': app_id})
        inputs.append({'type': "AutoDetectBMPFlag", 'value': auto_detect_bmp})
        inputs.append({'type': "EnableReinjectionFlag",
                       'value': enable_reinjection})

        return inputs

    @staticmethod
    def create_list_of_algorithms():
        """

        :return:
        """
        algorithms = \
            "FrontEndCommonMachineInterfacer," \
            "FrontEndCommonApplicationRunner," \
            "FrontEndCommonPartitionableGraphApplicationDataLoader," \
            "FrontEndCommonPartitionableGraphHostExecuteDataSpecification," \
            "FrontEndCommomLoadExecutableImages," \
            "FrontEndCommonRoutingTableLoader,FrontEndCommonTagsLoader," \
            "FrontEndCommomPartitionableGraphDataSpecificationWriter," \
            "FrontEndCommonBufferManagerCreater," \
            "FrontEndCommonNotificationProtocol"
        return algorithms

    @staticmethod
    def _create_pacman_outputs():
        """

        :return:
        """
        required_outputs = list()
        required_outputs.append("RanToken")
        return required_outputs