from spinn_front_end_common.utilities import helpful_functions


class Reload(object):
    """ Reload functions for reload scripts
    """

    def __init__(
            self, machine_name, version, reports_states, bmp_details,
            down_chips, down_cores, number_of_boards, height, width,
            auto_detect_bmp, enable_reinjection, xml_paths,
            scamp_connection_data, boot_port_num, verify, router_tables,
            executable_targets, tags, iptags, reverse_iptags, placements,
            app_folder, wait_for_read_confirmation, socket_addresses,
            database_file_path, runtime, time_scale_factor,
            send_start_notification, reset_machine_on_start_up,
            processor_to_app_data_base_address, placement_to_app_data_files,
            dsg_targets, loading=True, running=True, app_id=30):

        if scamp_connection_data == "None":
            scamp_connection_data = None

        pacman_inputs = self._create_pacman_inputs(
            machine_name, version, reports_states, bmp_details,
            down_chips, down_cores, number_of_boards, height, width,
            auto_detect_bmp, enable_reinjection, app_id, scamp_connection_data,
            boot_port_num, placement_to_app_data_files, verify, router_tables,
            processor_to_app_data_base_address, executable_targets, tags,
            iptags, reverse_iptags, placements, app_folder,
            wait_for_read_confirmation, socket_addresses, database_file_path,
            runtime, time_scale_factor, send_start_notification,
            reset_machine_on_start_up, loading, running, dsg_targets)
        pacman_outputs = self._create_pacman_outputs(loading, running)

        # get the list of algorithms expected to be used
        pacman_algorithms = self.create_list_of_algorithms(
            loading, running, dsg_targets)

        # create prov listing
        prov_listing = list()

        # run the pacman executor
        helpful_functions.do_mapping(
            pacman_inputs, pacman_algorithms, pacman_outputs, xml_paths,
            False, prov_listing)

    @staticmethod
    def _create_pacman_inputs(
            machine_name, version, reports_states, bmp_details,
            down_chips, down_cores, number_of_boards, height, width,
            auto_detect_bmp, enable_reinjection, app_id, scamp_connection_data,
            boot_port_num, placement_to_app_data_files, verify, router_tables,
            processor_to_app_data_base_address, executable_targets,
            buffered_tags, iptags, reverse_iptags, placements, app_folder,
            wait_for_read_confirmation, socket_addresses, database_file_path,
            runtime, time_scale_factor, send_start_notification,
            reset_machine_on_start_up, loading, running, dsg_targets):
        inputs = list()
        if loading:
            inputs.append({'type': "NoSyncChanges", 'value': 0})
            inputs.append({'type': "ReportStates", 'value': reports_states})
            inputs.append({'type': 'IPAddress', 'value': machine_name})
            inputs.append({'type': "BoardVersion", 'value': version})
            inputs.append({'type': "BMPDetails", 'value': bmp_details})
            inputs.append({'type': "DownedChipsDetails", 'value': down_chips})
            inputs.append({'type': "DownedCoresDetails", 'value': down_cores})
            inputs.append({'type': "NumberOfBoards",
                           'value': number_of_boards})
            inputs.append({'type': "MachineWidth", 'value': width})
            inputs.append({'type': "MachineHeight", 'value': height})
            inputs.append({'type': "APPID", 'value': app_id})
            inputs.append({'type': "AutoDetectBMPFlag",
                           'value': auto_detect_bmp})
            inputs.append({'type': "EnableReinjectionFlag",
                           'value': enable_reinjection})
            inputs.append({'type': "ScampConnectionData",
                           'value': scamp_connection_data})
            inputs.append({"type": "BootPortNum", 'value': boot_port_num})
            inputs.append({'type': "WriteCheckerFlag", 'value': verify})
            inputs.append({'type': "ExecutableTargets",
                           "value": executable_targets})
            inputs.append({"type": "MemoryRoutingTables",
                           'value': router_tables})
            inputs.append({'type': "MemoryTags", 'value': buffered_tags})
            inputs.append({'type': "MemoryIpTags", 'value': iptags})
            inputs.append({"type": "MemoryReverseTags",
                           'value': reverse_iptags})
            inputs.append({'type': "MemoryPlacements", 'value': placements})
            inputs.append({'type': "ApplicationDataFolder",
                           "value": app_folder})
            inputs.append({'type': "DatabaseWaitOnConfirmationFlag",
                           'value': wait_for_read_confirmation})
            inputs.append({'type': "DatabaseSocketAddresses",
                           'value': socket_addresses})
            inputs.append({'type': "DatabaseFilePath",
                           'value': database_file_path})
            inputs.append({"type": "RunTime", 'value': runtime})
            inputs.append({'type': "TimeScaleFactor",
                           'value': time_scale_factor})
            inputs.append({'type': "SendStartNotifications",
                           'value': send_start_notification})
            inputs.append({'type': "ResetMachineOnStartupFlag",
                           'value': reset_machine_on_start_up})

            if placement_to_app_data_files is not None:
                inputs.append({'type': "PlacementToAppDataFilePaths",
                               'value': placement_to_app_data_files})

            if processor_to_app_data_base_address is not None:
                inputs.append({'type': "ProcessorToAppDataBaseAddress",
                               'value': processor_to_app_data_base_address})

            if dsg_targets is not None:
                inputs.append({'type': "DataSpecificationTargets",
                               'value': dsg_targets})

        if running and not loading:
            inputs.append({'type': "LoadedIPTagsToken", "value": True})
            inputs.append({'type': "LoadedReverseIPTagsToken", "value": True})
            inputs.append({'type': "LoadedRoutingTablesToken", "value": True})
            inputs.append({'type': "LoadBinariesToken", "value": True})
            inputs.append({'type': "LoadedApplicationDataToken",
                           "value": True})
        return inputs

    @staticmethod
    def create_list_of_algorithms(loading, running, dsg_targets):
        algorithms = list()
        if loading:
            algorithms.append(
                "FrontEndCommonPartitionableGraphApplicationDataLoader")
            algorithms.append("FrontEndCommomLoadExecutableImages")
            algorithms.append("FrontEndCommonRoutingTableLoader")
            algorithms.append("FrontEndCommonTagsLoaderSeperateLists")
            algorithms.append("MallocBasedChipIDAllocator")
            if dsg_targets is not None:
                algorithms.append(
                    "FrontEndCommonPartitionableGraphMachineExecuteDataSpecification")  # @IgnorePep8

        if running:
            algorithms.append("FrontEndCommonApplicationExiter")
            algorithms.append("FrontEndCommonBufferManagerCreater")
            algorithms.append("FrontEndCommonNotificationProtocol")
            algorithms.append("FrontEndCommonApplicationRunner")
            algorithms.append("FrontEndCommonMachineInterfacer")
        return algorithms

    @staticmethod
    def _create_pacman_outputs(loading, running):
        required_outputs = list()
        if loading:
            required_outputs.append("LoadedIPTagsToken")
            required_outputs.append("LoadedReverseIPTagsToken")
            required_outputs.append("LoadedRoutingTablesToken")
            required_outputs.append("LoadBinariesToken")
            required_outputs.append("LoadedApplicationDataToken")
        elif running:
            required_outputs.append("RanToken")
        return required_outputs
