from spinn_front_end_common.utilities.reload.reload_script import ReloadScript


class FrontEndCommonReloadScriptCreator(object):
    """ Create a reload script
    """

    __slots__ = []

    def __call__(
            self,

            # Machine information
            machine, machine_name, version, bmp_details, down_chips,
            down_cores, auto_detect_bmp, enable_reinjection,
            scamp_connection_data, boot_port_num,
            reset_machine_on_start_up, max_sdram_per_chip,

            # Load data information
            router_tables, tags, app_data_runtime_folder,
            dsg_targets, exec_dse_on_host, dse_app_id,

            # Buffer information
            buffer_manager, placements,

            # Database notification information
            wait_for_read_confirmation, database_socket_addresses,
            database_file_path, send_start_notification,

            # Execute information
            executable_targets, app_id, runtime, time_scale_factor,
            total_machine_timesteps, executable_finder, time_threshold
    ):

        reload_script = ReloadScript(

            machine_name, version, bmp_details, down_chips, down_cores,
            auto_detect_bmp, enable_reinjection, scamp_connection_data,
            boot_port_num,

            reset_machine_on_start_up, max_sdram_per_chip,
            app_data_runtime_folder, exec_dse_on_host, dse_app_id,

            wait_for_read_confirmation, database_file_path,
            send_start_notification,

            app_id, runtime, time_scale_factor, total_machine_timesteps,
            time_threshold)

        for ip_tag in tags.ip_tags:
            reload_script.add_ip_tag(ip_tag)

        for reverse_ip_tag in tags.reverse_ip_tags:
            reload_script.add_reverse_ip_tag(reverse_ip_tag)

        for router_table in router_tables.routing_tables:
            if not machine.get_chip_at(router_table.x, router_table.y).virtual:
                if len(router_table.multicast_routing_entries) > 0:
                    reload_script.add_routing_table(router_table)

        for socket_address in database_socket_addresses:
            reload_script.add_socket_address(socket_address)

        buffered_vertices_regions_file_paths = \
            buffer_manager.reload_buffer_files
        for buffered_vertex in buffer_manager.sender_vertices:
            tag = tags.get_ip_tags_for_vertex(buffered_vertex)[0]
            placement = placements.get_placement_of_vertex(buffered_vertex)
            reload_script.add_buffered_vertex(
                buffered_vertex, tag, placement,
                buffered_vertices_regions_file_paths[buffered_vertex])

        for ((x, y, p), file_path) in dsg_targets.iteritems():
            reload_script.add_dsg_target(x, y, p, file_path)

        for binary in executable_targets.binaries:
            reload_script.add_executable_target(
                executable_finder.get_executable_path(binary),
                executable_targets.get_cores_for_binary(binary))

        # end reload script
        reload_script.close()

        return True
