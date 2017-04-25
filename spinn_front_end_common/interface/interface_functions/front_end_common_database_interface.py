# pacman imports
from spinn_machine.utilities.progress_bar import ProgressBar

# front end common imports
from spinn_front_end_common.utilities.database.database_writer import \
    DatabaseWriter


class FrontEndCommonDatabaseInterface(object):
    """ Writes a database of the graph(s) and other information
    """

    __slots__ = [
        # the database writer object
        "_writer",

        # True if the end user has asked for the database to be written
        "_user_create_database",

        # True if the network is computed to need the database to be written
        "_needs_database"
    ]

    def __init__(self):
        self._writer = None
        self._user_create_database = None
        self._needs_database = None

    def __call__(
            self, machine_graph, user_create_database, tags,
            runtime, machine, time_scale_factor, machine_time_step,
            placements, routing_infos, router_tables, database_directory,
            create_atom_to_event_id_mapping=False, application_graph=None,
            graph_mapper=None):

        self._writer = DatabaseWriter(database_directory)
        self._user_create_database = user_create_database

        # add database generation if requested
        self._needs_database = \
            self._writer.auto_detect_database(machine_graph)
        if ((self._user_create_database == "None" and self._needs_database) or
                self._user_create_database == "True"):

            if (application_graph is not None and
                    application_graph.n_vertices != 0):
                database_progress = ProgressBar(11, "Creating database")
            else:
                database_progress = ProgressBar(10, "Creating database")

            self._writer.add_system_params(
                time_scale_factor, machine_time_step, runtime)
            database_progress.update()
            self._writer.add_machine_objects(machine)
            database_progress.update()
            if (application_graph is not None and
                    application_graph.n_vertices != 0):
                self._writer.add_application_vertices(application_graph)
                database_progress.update()
            self._writer.add_vertices(
                machine_graph, graph_mapper, application_graph)
            database_progress.update()
            self._writer.add_placements(placements, machine_graph)
            database_progress.update()
            self._writer.add_routing_infos(
                routing_infos, machine_graph)
            database_progress.update()
            self._writer.add_routing_tables(router_tables)
            database_progress.update()
            self._writer.add_tags(machine_graph, tags)
            database_progress.update()
            if (graph_mapper is not None and
                    application_graph is not None and
                    create_atom_to_event_id_mapping):
                self._writer.create_atom_to_event_id_mapping(
                    graph_mapper=graph_mapper,
                    application_graph=application_graph,
                    machine_graph=machine_graph,
                    routing_infos=routing_infos)
            database_progress.update()
            database_progress.update()
            database_progress.end()

        return self, self.database_file_path

    @property
    def database_file_path(self):
        if ((self._user_create_database == "None" and self._needs_database) or
                self._user_create_database == "True"):
            return self._writer.database_path
