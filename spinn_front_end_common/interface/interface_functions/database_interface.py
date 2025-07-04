# Copyright (c) 2015 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from typing import Optional, Set, Tuple
from spinn_utilities.config_holder import (
    get_config_bool, get_config_bool_or_none)
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from pacman.model.graphs.machine import MachineVertex
from spinn_front_end_common.utilities.database import DatabaseWriter
from spinn_front_end_common.abstract_models import (
    AbstractSupportsDatabaseInjection)
from spinn_front_end_common.data import FecDataView

logger = FormatAdapter(logging.getLogger(__name__))


def database_interface(runtime: Optional[float]) -> Optional[str]:
    """
    :param runtime:
    :return: where the database is located, if one is made
    """
    needs_db = DatabaseWriter.auto_detect_database()
    user_create_database = get_config_bool_or_none(
        "Database", "create_database")
    if user_create_database is not None:
        if user_create_database != needs_db:
            logger.warning(
                "Database creating changed to {} due to cfg settings",
                user_create_database)
            needs_db = user_create_database
    if not needs_db:
        return None

    with DatabaseWriter() as writer:
        logger.info("Creating live event connection database in {}",
                    writer.database_path)
        _write_to_db(writer, runtime)
        return writer.database_path


def _write_to_db(w: DatabaseWriter, runtime: Optional[float]) -> None:
    with ProgressBar(6, "Creating graph description database") as p:
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
            machine_vertices: Set[Tuple[MachineVertex, str]] = {
                (vertex, vertex.injection_partition_id)
                for vertex in FecDataView.iterate_machine_vertices()
                if isinstance(vertex, AbstractSupportsDatabaseInjection)
                and vertex.is_in_injection_mode}
            machine_vertices.update(lpg_source_machine_vertices)
            live_vertices = FecDataView.iterate_live_output_vertices()
            for vertex, part_id in live_vertices:
                machine_vertices.update(
                    (m_vertex, part_id)
                    for m_vertex in vertex.splitter.get_out_going_vertices(
                        part_id))
            w.create_atom_to_event_id_mapping(machine_vertices)
            w.create_device_atom_event_id_mapping(
                FecDataView.iterate_live_output_devices())
        p.update()
