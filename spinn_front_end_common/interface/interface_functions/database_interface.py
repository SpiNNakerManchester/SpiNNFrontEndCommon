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
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.database import DatabaseWriter

logger = FormatAdapter(logging.getLogger(__name__))


def database_interface(tags, runtime, router_tables):
    """ Writes a database of the graph(s) and other information.

        :param ~pacman.model.tags.Tags tags:
        :param int runtime:
        :param router_tables:
        :type router_tables:
            ~pacman.model.routing_tables.MulticastRoutingTables
        :return: Database interface, where the database is located
        :rtype: tuple(DatabaseInterface, str)
    """
    interface = _DatabaseInterface()
    return interface._run(tags, runtime, router_tables)


class _DatabaseInterface(object):
    """ Writes a database of the graph(s) and other information.
    """

    __slots__ = [
        # the database writer object
        "_writer",

        # True if the network is computed to need the database to be written
        "_needs_db"
    ]

    def __init__(self):
        self._writer = DatabaseWriter()
        # add database generation if requested
        self._needs_db = self._writer.auto_detect_database()

    def _run(
            self, tags, runtime, router_tables):
        """
        :param ~pacman.model.tags.Tags tags:
        :param int runtime:
        :param router_tables:
        :type router_tables:
            ~pacman.model.routing_tables.MulticastRoutingTables
        :return: Database interface, where the database is located
        :rtype: tuple(DatabaseInterface, str)
        """
        # pylint: disable=too-many-arguments

        user_create_database = get_config_bool("Database", "create_database")
        if user_create_database is not None:
            if user_create_database != self._needs_db:
                logger.warning(f"Database creating changed to "
                               f"{user_create_database} due to cfg settings")
                self._needs_db = user_create_database

        if self._needs_db:
            logger.info("creating live event connection database in {}",
                        self._writer.database_path)
            self._write_to_db(runtime, router_tables, tags)

        if self._needs_db:
            return self._writer.database_path
        return None

    def _write_to_db(self, runtime, router_tables, tags):
        """
        :param int runtime:
        :param ~.MulticastRoutingTables router_tables:
        :param ~.Tags tags:
        """
        # pylint: disable=too-many-arguments

        view = FecDataView()
        app_graph = FecDataView.get_runtime_graph()
        machine_graph = FecDataView.get_runtime_machine_graph()
        with self._writer as w, ProgressBar(
                9, "Creating graph description database") as p:
            w.add_system_params(runtime, FecDataView.get_app_id())
            p.update()
            w.add_machine_objects()
            p.update()
            if app_graph is not None and app_graph.n_vertices:
                w.add_application_vertices(app_graph)
            p.update()
            w.add_vertices(machine_graph, view.max_run_time_steps, app_graph)
            p.update()
            w.add_placements()
            p.update()
            w.add_routing_infos(machine_graph)
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
                        machine_graph=machine_graph)
            p.update()
