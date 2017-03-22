from pacman.executor.pacman_algorithm_executor import PACMANAlgorithmExecutor
from spinn_front_end_common.utilities import helpful_functions


class Reload(object):
    """ Reload functions for reload scripts
    """

    def __init__(
            self,

            # Machine information
            machine_name, version, bmp_details, down_chips, down_cores,
            auto_detect_bmp, enable_reinjection, scamp_connection_data,
            boot_port_num, reset_machine_on_start_up, max_sdram_per_chip,

            # Load data information
            router_tables, iptags, reverse_iptags, app_data_runtime_folder,
            dsg_targets, exec_dse_on_host, dse_app_id,

            # Buffer information
            buffered_tags, buffered_placements,

            # Database notification information
            wait_for_read_confirmation, database_socket_addresses,
            database_file_path, send_start_notification,

            # Execute information
            executable_targets, app_id, runtime, time_scale_factor,
            total_machine_timesteps, time_threshold,

            # Flags that indicate what to actually do
            running=True, loading=True):

        if machine_name == "None":
            raise Exception(
                "This reload script was created using a virtual board.  To"
                " use it, please set machine_name to the hostname or IP"
                " address of a real board")

        if scamp_connection_data == "None":
            scamp_connection_data = None

        inputs = dict()

        # Machine inputs
        inputs['IPAddress'] = machine_name
        inputs["BoardVersion"] = version
        inputs["BMPDetails"] = bmp_details
        inputs["DownedChipsDetails"] = down_chips
        inputs["DownedCoresDetails"] = down_cores
        inputs["AutoDetectBMPFlag"] = auto_detect_bmp
        inputs["EnableReinjectionFlag"] = enable_reinjection
        inputs["ScampConnectionData"] = scamp_connection_data
        inputs["BootPortNum"] = boot_port_num
        inputs["ResetMachineOnStartupFlag"] = reset_machine_on_start_up
        inputs["MaxSDRAMSize"] = max_sdram_per_chip

        # Loading inputs
        inputs["MemoryRoutingTables"] = router_tables
        inputs["MemoryIpTags"] = iptags
        inputs["MemoryReverseTags"] = reverse_iptags
        inputs["ApplicationDataFolder"] = app_data_runtime_folder
        inputs["DataSpecificationTargets"] = dsg_targets
        inputs["WriteTextSpecsFlag"] = False
        inputs["WriteMemoryMapReportFlag"] = False
        inputs["DSEAPPID"] = dse_app_id
        inputs["ReportFolder"] = None

        # Buffered inputs
        inputs["MemoryTags"] = buffered_tags
        inputs["MemoryPlacements"] = buffered_placements
        inputs["WriteReloadFilesFlag"] = False

        # Database notification inputs
        inputs["DatabaseSocketAddresses"] = database_socket_addresses
        inputs["DatabaseWaitOnConfirmationFlag"] = wait_for_read_confirmation
        inputs["SendStartNotifications"] = send_start_notification
        inputs["DatabaseFilePath"] = database_file_path

        # Execute inputs
        inputs["APPID"] = app_id
        inputs["NoSyncChanges"] = 0
        inputs["TimeScaleFactor"] = time_scale_factor
        inputs["RunTime"] = runtime
        inputs["TotalMachineTimeSteps"] = total_machine_timesteps
        inputs["ExecutableTargets"] = executable_targets
        inputs["PostSimulationOverrunBeforeError"] = time_threshold

        algorithms = list()
        algorithms.append("FrontEndCommonMachineGenerator")
        algorithms.append("MallocBasedChipIDAllocator")

        if loading:
            algorithms.append("FrontEndCommonRoutingTableLoader")
            algorithms.append("FrontEndCommonTagsLoaderSeparateLists")
            if exec_dse_on_host:
                algorithms.append(
                    "FrontEndCommonHostExecuteDataSpecification")
            else:
                algorithms.append(
                    "FrontEndCommonMachineExecuteDataSpecification")
        else:
            inputs["LoadedApplicationDataToken"] = True
            inputs["LoadedRoutingTablesToken"] = True
            inputs["LoadedIPTagsToken"] = True
            inputs["LoadedReverseIPTagsToken"] = True

        if running:
            algorithms.append("FrontEndCommonBufferManagerCreator")
            algorithms.append("FrontEndCommonLoadExecutableImages")
            algorithms.append("FrontEndCommonNotificationProtocol")
            algorithms.append("FrontEndCommonChipRuntimeUpdater")
            algorithms.append("FrontEndCommonApplicationRunner")

        # run the pacman executor
        xml_paths = helpful_functions.get_front_end_common_pacman_xml_paths()
        executer = PACMANAlgorithmExecutor(
            algorithms=algorithms, optional_algorithms=[], inputs=inputs,
            required_outputs=[], xml_paths=xml_paths, packages=None,
            do_timings=False, print_timings=False)
        executer.execute_mapping()
