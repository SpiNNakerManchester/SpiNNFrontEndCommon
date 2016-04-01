# pacman imports
from spinn_machine.utilities.progress_bar import ProgressBar

# front end common imports
from spinn_front_end_common.utilities.database.database_writer import \
    DatabaseWriter


class FrontEndCommonDatabaseInterface(object):
    """ Writes a database of the graph(s) and other information
    """

    def __init__(self):
        self._writer = None
        self._user_create_database = None
        self._needs_database = None

    def __call__(
            self, partitioned_graph, user_create_database, tags,
            runtime, machine, time_scale_factor, machine_time_step,
            placements, routing_infos, router_tables, database_directory,
            create_atom_to_event_id_mapping=False, partitionable_graph=None,
            graph_mapper=None):

        self._writer = DatabaseWriter(database_directory)
        self._user_create_database = user_create_database

        # add database generation if requested
        self._needs_database = \
            self._writer.auto_detect_database(partitioned_graph)
        if ((self._user_create_database == "None" and self._needs_database) or
                self._user_create_database == "True"):

            if (partitionable_graph is not None and
                    len(partitionable_graph.vertices) != 0):
                database_progress = ProgressBar(11, "Creating database")
            else:
                database_progress = ProgressBar(10, "Creating database")

            self._writer.add_system_params(
                time_scale_factor, machine_time_step, runtime)
            database_progress.update()
            self._writer.add_machine_objects(machine)
            database_progress.update()
            if (partitionable_graph is not None and
                    len(partitionable_graph.vertices) != 0):
                self._writer.add_partitionable_vertices(partitionable_graph)
                database_progress.update()
            self._writer.add_partitioned_vertices(
                partitioned_graph, graph_mapper, partitionable_graph)
            database_progress.update()
            self._writer.add_placements(placements, partitioned_graph)
            database_progress.update()
            self._writer.add_routing_infos(
                routing_infos, partitioned_graph)
            database_progress.update()
            self._writer.add_routing_tables(router_tables)
            database_progress.update()
            self._writer.add_tags(partitioned_graph, tags)
            database_progress.update()
            if (graph_mapper is not None and
                    partitionable_graph is not None and
                    create_atom_to_event_id_mapping):
                self._writer.create_atom_to_event_id_mapping(
                    graph_mapper=graph_mapper,
                    partitionable_graph=partitionable_graph,
                    partitioned_graph=partitioned_graph,
                    routing_infos=routing_infos)
            database_progress.update()
            database_progress.update()
            database_progress.end()

        return {"database_interface": self,
                "database_file_path": self.database_file_path}

    @property
    def database_file_path(self):
        """

        :return:
        """
        if ((self._user_create_database == "None" and self._needs_database) or
                self._user_create_database == "True"):
            return self._writer.database_path
