# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.utilities.database import DatabaseWriter

logger = FormatAdapter(logging.getLogger(__name__))


class DatabaseInterface(object):
    """ Writes a database of the graph(s) and other information
    """

    __slots__ = [
        # the database writer object
        "_writer",

        # True if the end user has asked for the database to be written
        "_user_create_database",

        # True if the network is computed to need the database to be written
        "_needs_db"
    ]

    def __init__(self):
        self._writer = None
        self._user_create_database = None
        self._needs_db = None

    def __call__(
            self, machine_graph, user_create_database, tags,
            runtime, machine, data_n_timesteps, time_scale_factor,
            machine_time_step, placements, routing_infos, router_tables,
            database_directory, create_atom_to_event_id_mapping=False,
            application_graph=None, graph_mapper=None):
        # pylint: disable=too-many-arguments

        self._writer = DatabaseWriter(database_directory)
        self._user_create_database = user_create_database
        # add database generation if requested
        self._needs_db = self._writer.auto_detect_database(machine_graph)

        if self.needs_database:
            logger.info("creating live event connection database in {}",
                        self._writer.database_path)
            self._write_to_db(machine, time_scale_factor, machine_time_step,
                              runtime, application_graph, machine_graph,
                              data_n_timesteps, graph_mapper, placements,
                              routing_infos, router_tables, tags,
                              create_atom_to_event_id_mapping)

        return self, self.database_file_path

    @property
    def needs_database(self):
        if self._user_create_database == "None":
            return self._needs_db
        return self._user_create_database == "True"

    @property
    def database_file_path(self):
        if self.needs_database:
            return self._writer.database_path
        return None

    def _write_to_db(
            self, machine, time_scale_factor, machine_time_step,
            runtime, application_graph, machine_graph, data_n_timesteps,
            graph_mapper, placements, routing_infos, router_tables, tags,
            create_atom_to_event_id_mapping):
        """
        :param machine:
        :param time_scale_factor:
        :param machine_time_step:
        :param runtime:
        :param application_graph:
        :param machine_graph:
        :param data_n_timesteps: \
            The number of timesteps for which data space will been reserved
        :param graph_mapper:
        :param placements:
        :param routing_infos:
        :param router_tables:
        :param tags:
        :param create_atom_to_event_id_mapping:
        :return:
        """
        # pylint: disable=too-many-arguments

        with self._writer as w, ProgressBar(
                9, "Creating graph description database") as p:
            w.add_system_params(time_scale_factor, machine_time_step, runtime)
            p.update()
            w.add_machine_objects(machine)
            p.update()
            if application_graph is not None and application_graph.n_vertices:
                w.add_application_vertices(application_graph)
            p.update()
            w.add_vertices(machine_graph, data_n_timesteps, graph_mapper,
                           application_graph)
            p.update()
            w.add_placements(placements)
            p.update()
            w.add_routing_infos(routing_infos, machine_graph)
            p.update()
            w.add_routing_tables(router_tables)
            p.update()
            w.add_tags(machine_graph, tags)
            p.update()
            if (graph_mapper is not None and application_graph is not None
                    and create_atom_to_event_id_mapping):
                w.create_atom_to_event_id_mapping(
                    graph_mapper=graph_mapper,
                    application_graph=application_graph,
                    machine_graph=machine_graph, routing_infos=routing_infos)
            p.update()
