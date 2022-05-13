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
from spinn_front_end_common.abstract_models import (
    AbstractSupportsDatabaseInjection)

logger = FormatAdapter(logging.getLogger(__name__))


def database_interface(
        tags, runtime, machine, placements, routing_infos, app_id,
        application_graph, lpg_for_m_vertex):
    """
    :param ~pacman.model.tags.Tags tags:
    :param int runtime:
    :param ~spinn_machine.Machine machine:
    :param ~pacman.model.placements.Placements placements:
    :param ~pacman.model.routing_info.RoutingInfo routing_infos:
    :param int app_id:
    :param ~pacman.model.graphs.application.ApplicationGraph application_graph:
    :param dict(MachineVertex,LivePacketGatherMachineVertex) lpg_for_m_vertex:
    :return: Database interface, where the database is located
    :rtype: tuple(DatabaseInterface, str)
    """
    # pylint: disable=too-many-arguments
    writer = DatabaseWriter()
    needs_db = writer.auto_detect_database(
        application_graph, lpg_for_m_vertex)
    user_create_database = get_config_bool("Database", "create_database")
    if user_create_database is not None:
        if user_create_database != needs_db:
            logger.warning(f"Database creating changed to "
                           f"{user_create_database} due to cfg settings")
            needs_db = user_create_database

    if needs_db:
        logger.info("Creating live event connection database in {}",
                    writer.database_path)
        _write_to_db(
            writer, machine, runtime, application_graph, placements,
            routing_infos, tags, app_id, lpg_for_m_vertex)

    if needs_db:
        return writer.database_path
    return None


def _write_to_db(
        writer, machine, runtime, app_graph, placements, routing_infos, tags,
        app_id, lpg_for_m_vertex):
    """
    :param ~.Machine machine:
    :param int runtime:
    :param ~.ApplicationGraph app_graph:
    :param int data_n_timesteps:
        The number of timesteps for which data space will been reserved
    :param ~.Placements placements:
    :param ~.RoutingInfo routing_infos:
    :param ~.MulticastRoutingTables router_tables:
    :param ~.Tags tags:
    :param int app_id:
    :param dict(MachineVertex,LivePacketGatherMachineVertex) lpg_for_m_vertex:
    """
    # pylint: disable=too-many-arguments

    with writer as w, ProgressBar(
            6, "Creating graph description database") as p:
        w.add_system_params(runtime, app_id)
        p.update()
        w.add_machine_objects(machine)
        p.update()
        w.add_application_vertices(app_graph)
        p.update()
        w.add_placements(placements)
        p.update()
        w.add_tags(tags)
        p.update()
        if lpg_for_m_vertex is not None:
            w.add_lpg_mapping(lpg_for_m_vertex)
        if get_config_bool(
                "Database", "create_routing_info_to_neuron_id_mapping"):
            machine_vertices = list()
            if lpg_for_m_vertex is not None:
                machine_vertices.extend(lpg_for_m_vertex.keys())
            machine_vertices.extend(
                (vertex, vertex.injection_partition_id)
                for app_vertex in app_graph.vertices
                for vertex in app_vertex.machine_vertices
                if isinstance(vertex, AbstractSupportsDatabaseInjection)
                and vertex.is_in_injection_mode)
            w.create_atom_to_event_id_mapping(
                machine_vertices, routing_infos)
        p.update()
