from spinn_front_end_common.utilities.reload.reload_script import ReloadScript


class FrontEndCommonReloadScriptCreator(object):
    """ Create a reload script
    """

    def __call__(
            self, tags, app_data_folder, hostname, board_version,
            bmp_details, downed_chips, downed_cores, number_of_boards,
            height, width, auto_detect_bmp, enable_reinjection,
            processor_to_app_data_base_address, placements, router_tables,
            machine, executable_targets, run_time, time_scale_factor,
            database_socket_addresses, wait_on_confirmation,
            placement_to_app_data_files, buffer_manager, scamp_connection_data,
            boot_port_num, verify, database_file_path, send_start_notification):

        reload_script = ReloadScript(
            app_data_folder, hostname, board_version, bmp_details,
            downed_chips, downed_cores, number_of_boards, height, width,
            auto_detect_bmp, enable_reinjection, scamp_connection_data,
            boot_port_num, placement_to_app_data_files, verify,
            processor_to_app_data_base_address, executable_targets,
            wait_on_confirmation, database_file_path, run_time,
            time_scale_factor, send_start_notification, )

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
            placement = placements.get_placement_of_subvertex(buffered_vertex)
            reload_script.add_buffered_vertex(
                buffered_vertex, tag, placement,
                buffered_vertices_regions_file_paths[buffered_vertex])

        # end reload script
        reload_script.close()

        return {"ReloadToken": True}
