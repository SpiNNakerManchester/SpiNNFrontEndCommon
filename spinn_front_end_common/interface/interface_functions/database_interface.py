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
from spinn_front_end_common.utilities.globals_variables import get_simulator
from spinn_front_end_common.interface.interface_functions.spalloc_allocator \
    import (
        SpallocJobController)

logger = FormatAdapter(logging.getLogger(__name__))


def database_interface(
        machine_graph, tags, runtime, machine, data_n_timesteps, placements,
        routing_infos, router_tables, app_id, application_graph=None):
    """ Writes a database of the graph(s) and other information.

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
        :param int app_id:
        :param application_graph:
        :type application_graph:
            ~pacman.model.graphs.application.ApplicationGraph
        :return: Database interface, where the database is located
        :rtype: tuple(DatabaseInterface, str)
    """
    interface = _DatabaseInterface(machine_graph)
    # pylint: disable=protected-access
    return interface._run(
        machine_graph, tags, runtime, machine, data_n_timesteps, placements,
        routing_infos, router_tables, app_id, application_graph)


class _DatabaseInterface(object):
    """ Writes a database of the graph(s) and other information.
    """

    __slots__ = [
        # the database writer object
        "_writer",

        # True if the network is computed to need the database to be written
        "_needs_db"
    ]

    def __init__(self, machine_graph):
        self._writer = DatabaseWriter()
        # add database generation if requested
        self._needs_db = self._writer.auto_detect_database(machine_graph)

    def _run(
            self, machine_graph, tags, runtime, machine, data_n_timesteps,
            placements, routing_infos, router_tables, app_id,
            application_graph=None):
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
        :param int app_id:
        :param application_graph:
        :type application_graph:
            ~pacman.model.graphs.application.ApplicationGraph
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
            mac = get_simulator()._machine_allocation_controller
            job = None
            if mac and isinstance(mac, SpallocJobController):
                job = mac._job
            self._write_to_db(
                machine, runtime, application_graph, machine_graph,
                data_n_timesteps, placements, routing_infos, router_tables,
                tags, app_id, job)

        if self._needs_db:
            return self._writer.database_path
        return None

    def _write_to_db(
            self, machine, runtime, app_graph, machine_graph,
            data_n_timesteps, placements, routing_infos, router_tables,
            tags, app_id, job):
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
        :param int app_id:
        :param SpallocJob job:
        """
        # pylint: disable=too-many-arguments

        with self._writer as w, ProgressBar(
                9, "Creating graph description database") as p:
            w.add_system_params(runtime, app_id)
            w.add_proxy_configuration(job)
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
