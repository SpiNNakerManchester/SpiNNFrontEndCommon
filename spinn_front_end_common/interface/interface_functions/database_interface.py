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
from spinn_utilities.config_holder import get_config_bool
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.utilities.database import DatabaseWriter

logger = FormatAdapter(logging.getLogger(__name__))


class DatabaseInterface(object):
    """ Writes a database of the graph(s) and other information.
    """

    __slots__ = [
        # the database writer object
        "_writer",

        # True if the network is computed to need the database to be written
        "_needs_db"
    ]

    def __init__(self):
        self._writer = None
        self._needs_db = None

    def __call__(
            self, machine_graph, tags, runtime, machine, data_n_timesteps,
            placements, routing_infos, router_tables,
            report_folder, application_graph=None):
        """
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
        :param ~pacman.model.tags.Tags tags:
        :param int runtime:
        :param ~spinn_machine.Machine machine:
        :param int data_n_timesteps:
        :param ~pacman.model.placements.Placements placements:
        :param ~pacman.model.routing_info.RoutingInfo routing_infos:
        :param router_tables:
        :type router_tables:
            ~pacman.model.routing_tables.MulticastRoutingTables
        :param str report_folder: Where the database will be put.
        :param application_graph:
        :type application_graph:
            ~pacman.model.graphs.application.ApplicationGraph
        :return: Database interface, where the database is located
        :rtype: tuple(DatabaseInterface, str)
        """
        # pylint: disable=too-many-arguments

        self._writer = DatabaseWriter(report_folder)
        # add database generation if requested
        self._needs_db = self._writer.auto_detect_database(machine_graph)
        user_create_database = get_config_bool("Database", "create_database")
        if user_create_database is not None:
            if user_create_database != self._needs_db:
                logger.warning(f"Database creating changed to "
                               f"{user_create_database} due to cfg settings")
                self._needs_db = user_create_database

        if self._needs_db:
            logger.info("creating live event connection database in {}",
                        self._writer.database_path)
            self._write_to_db(
                machine, runtime, application_graph, machine_graph,
                data_n_timesteps, placements, routing_infos, router_tables,
                tags)

        return self, self.database_file_path

    @property
    def database_file_path(self):
        """
        :rtype: str or None
        """
        if self._needs_db:
            return self._writer.database_path
        return None

    def _write_to_db(
            self, machine, runtime, app_graph, machine_graph,
            data_n_timesteps, placements, routing_infos, router_tables,
            tags):
        """
        :param ~.Machine machine:
        :param int runtime:
        :param ~.ApplicationGraph app_graph:
        :param ~.MachineGraph machine_graph:
        :param int data_n_timesteps:
            The number of timesteps for which data space will been reserved
        :param ~.Placements placements:
        :param ~.RoutingInfo routing_infos:
        :param ~.MulticastRoutingTables router_tables:
        :param ~.Tags tags:
        """
        # pylint: disable=too-many-arguments

        with self._writer as w, ProgressBar(
                9, "Creating graph description database") as p:
            w.add_system_params(runtime)
            p.update()
            w.add_machine_objects(machine)
            p.update()
            if app_graph is not None and app_graph.n_vertices:
                w.add_application_vertices(app_graph)
            p.update()
            w.add_vertices(machine_graph, data_n_timesteps, app_graph)
            p.update()
            w.add_placements(placements)
            p.update()
            w.add_routing_infos(routing_infos, machine_graph)
            p.update()
            w.add_routing_tables(router_tables)
            p.update()
            w.add_tags(machine_graph, tags)
            p.update()
            if app_graph is not None:
                if get_config_bool(
                        "Database",
                        "create_routing_info_to_neuron_id_mapping"):
                    w.create_atom_to_event_id_mapping(
                        application_graph=app_graph,
                        machine_graph=machine_graph,
                        routing_infos=routing_infos)
            p.update()
