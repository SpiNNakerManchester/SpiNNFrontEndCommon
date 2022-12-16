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
from spinn_front_end_common.data import FecDataView

logger = FormatAdapter(logging.getLogger(__name__))


def database_interface(runtime):
    """
    :param ~pacman.model.tags.Tags tags:
    :return: Database interface, where the database is located
    :rtype: tuple(DatabaseInterface, str)
    """
    # pylint: disable=too-many-arguments
    needs_db = DatabaseWriter.auto_detect_database()
    user_create_database = get_config_bool("Database", "create_database")
    if user_create_database is not None:
        if user_create_database != needs_db:
            logger.warning(f"Database creating changed to "
                           f"{user_create_database} due to cfg settings")
            needs_db = user_create_database

    if needs_db:
        writer = DatabaseWriter()
        logger.info("Creating live event connection database in {}",
                    writer.database_path)
        _write_to_db(writer, runtime)
        writer.close()
        return writer.database_path
    return None


def _write_to_db(writer, runtime):
    """
    :param DatabaseWriter writer:
    :param int runtime:
    """

    with writer as w, ProgressBar(
            6, "Creating graph description database") as p:
        w.add_system_params(runtime)
        w.add_proxy_configuration()
        p.update()
        w.add_machine_objects()
        p.update()
        w.add_application_vertices()
        p.update()
        w.add_placements()
        p.update()
        w.add_tags()
        p.update()
        lpg_source_machine_vertices = w.add_lpg_mapping()

        if get_config_bool(
                "Database", "create_routing_info_to_neuron_id_mapping"):
            machine_vertices = {
                (vertex, vertex.injection_partition_id)
                for vertex in FecDataView.iterate_machine_vertices()
                if isinstance(vertex, AbstractSupportsDatabaseInjection)
                and vertex.is_in_injection_mode}
            machine_vertices.update(lpg_source_machine_vertices)
            live_vertices = FecDataView.iterate_live_output_vertices()
            machine_vertices.update(
                (m_vertex, part_id)
                for vertex, part_id in live_vertices
                for m_vertex in vertex.machine_vertices)
            w.create_atom_to_event_id_mapping(machine_vertices)
        p.update()
