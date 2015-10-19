"""
FrontEndCommonDatabaseInterface
"""

# pacman imports
from pacman.utilities.utility_objs.progress_bar import ProgressBar

# front end common imports
from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities.database.database_writer import \
    DatabaseWriter


class FrontEndCommonDatabaseInterface(object):
    """
    FrontEndCommonDatabaseInterface
    """
    
    def __call__(
            self, partitioned_graph, user_create_database, tags,
            runtime, machine, time_scale_factor, machine_time_step,
            partitionable_graph, graph_mapper, placements, routing_infos,
            router_tables, execute_mapping, database_directory,
            wait_for_read_confirmation, socket_addresses):
        
        writer = DatabaseWriter(
            database_directory, wait_for_read_confirmation, socket_addresses)
        
        # add database generation if requested
        needs_database = \
            helpful_functions.auto_detect_database(partitioned_graph)
        if ((user_create_database == "None" and needs_database) or
                user_create_database == "True"):

            database_progress = ProgressBar(10, "Creating database")

            writer.add_system_params(
                time_scale_factor, machine_time_step, runtime)
            database_progress.update()
            writer.add_machine_objects(machine)
            database_progress.update()
            writer.add_partitioned_vertices(
                partitioned_graph, graph_mapper, partitionable_graph)
            database_progress.update()
            writer.add_placements(placements, partitioned_graph)
            database_progress.update()
            writer.add_routing_infos(
                routing_infos, partitioned_graph)
            database_progress.update()
            writer.add_routing_tables(router_tables)
            database_progress.update()
            writer.add_tags(partitioned_graph, tags)
            database_progress.update()
            if execute_mapping:
                writer.create_atom_to_event_id_mapping(
                    graph_mapper=graph_mapper,
                    partitionable_graph=partitionable_graph,
                    partitioned_graph=partitioned_graph,
                    routing_infos=routing_infos)
            database_progress.update()
            database_progress.update()
            database_progress.end()
            writer.send_read_notification()

        return {"database_interface": self}
