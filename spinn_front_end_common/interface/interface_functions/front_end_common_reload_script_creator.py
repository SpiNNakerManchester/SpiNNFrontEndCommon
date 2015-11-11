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
            vertex_to_app_data_files, buffer_manager):

        reload_script = ReloadScript(
            app_data_folder, hostname, board_version, bmp_details,
            downed_chips, downed_cores, number_of_boards, height, width,
            auto_detect_bmp, enable_reinjection)

        reload_script.runtime = run_time
        reload_script.time_scale_factor = time_scale_factor
        reload_script.wait_on_confirmation = wait_on_confirmation

        for ip_tag in tags.ip_tags:
            reload_script.add_ip_tag(ip_tag)

        for reverse_ip_tag in tags.reverse_ip_tags:
            reload_script.add_reverse_ip_tag(reverse_ip_tag)

        for placement in placements:
            key = (placement.x, placement.y, placement.p)
            start_address = \
                processor_to_app_data_base_address[key]['start_address']
            file_paths = vertex_to_app_data_files[placement.subvertex]
            for file_path in file_paths:
                reload_script.add_application_data(
                    file_path, placement, start_address)

        for router_table in router_tables.routing_tables:
            if not machine.get_chip_at(router_table.x, router_table.y).virtual:
                if len(router_table.multicast_routing_entries) > 0:
                    reload_script.add_routing_table(router_table)

        for executable_target_key in executable_targets.binary_paths():
            core_subset = executable_targets.\
                retrieve_cores_for_a_executable_target(executable_target_key)
            reload_script.add_binary(executable_target_key, core_subset)

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
