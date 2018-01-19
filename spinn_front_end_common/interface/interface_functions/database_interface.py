# utilities imports
from spinn_utilities.progress_bar import ProgressBar

# front end common imports
from spinn_front_end_common.utilities.database import DatabaseWriter


class DatabaseInterface(object):
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
        self._needs_database = self._writer.auto_detect_database(
            machine_graph)

        if self.needs_database:
            with self._writer as w, ProgressBar(9, "Creating database") as p:
                w.add_system_params(
                    time_scale_factor, machine_time_step, runtime)
                p.update()
                w.add_machine_objects(machine)
                p.update()
                if application_graph is not None \
                        and application_graph.n_vertices:
                    w.add_application_vertices(application_graph)
                p.update()
                w.add_vertices(machine_graph, graph_mapper, application_graph)
                p.update()
                w.add_placements(placements)
                p.update()
                w.add_routing_infos(routing_infos, machine_graph)
                p.update()
                w.add_routing_tables(router_tables)
                p.update()
                w.add_tags(machine_graph, tags)
                p.update()
                if (graph_mapper is not None
                        and application_graph is not None
                        and create_atom_to_event_id_mapping):
                    w.create_atom_to_event_id_mapping(
                        graph_mapper=graph_mapper,
                        application_graph=application_graph,
                        machine_graph=machine_graph,
                        routing_infos=routing_infos)
                p.update()

        return self, self.database_file_path

    @property
    def needs_database(self):
        return ((self._user_create_database == "None" and self._needs_database)
                or self._user_create_database == "True")

    @property
    def database_file_path(self):
        if self.needs_database:
            return self._writer.database_path
        return None
