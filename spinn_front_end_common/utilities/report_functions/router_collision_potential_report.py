# Copyright (c) 2019 The University of Manchester
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

import os
from collections import defaultdict
from spinn_machine.router import Router
from spinn_front_end_common.data import FecDataView

COLLISION_REPORT = "routing_collision_protential_report.rpt"


def router_collision_potential_report():
    file_name = os.path.join(
        FecDataView.get_run_dir_path(),
        "routing_collision_protential_report.rpt")
    with open(file_name, "w", encoding="utf-8") as writer:
        collision_counts = _generate_data()
        _write_report(collision_counts, writer)


def _write_report(collision_counts, writer):
    if len(collision_counts) == 0:
        writer.write("There are no collisions in this network mapping")
        return

    for (x, y) in collision_counts:
        for link_id in collision_counts[(x, y)]:
            writer.write(
                f"router {x}:{y} link {link_id} has potential "
                f"{collision_counts[(x, y)][link_id]} collisions\n")


def _generate_data():
    router_tables_by_partition = FecDataView.get_routing_table_by_partition()
    collisions = defaultdict(lambda: defaultdict(int))
    n_keys_map = dict()
    # https://github.com/SpiNNakerManchester/SpiNNFrontEndCommon/issues/891
    # use machine_vertex.get_n_keys_for_partition(identifier)
    for (x, y) in router_tables_by_partition.get_routers():
        for partition in \
                router_tables_by_partition.get_entries_for_router(x, y):
            entry = router_tables_by_partition.get_entry_on_coords_for_edge(
                partition, x, y)
            for link in entry.link_ids:
                if collisions[(x, y)][link] == 0:
                    chip = FecDataView.get_chip_at(x, y)
                    other_chip_x = chip.router.get_link(link).destination_x
                    other_chip_y = chip.router.get_link(link).destination_y
                    collision_route = Router.opposite(link)

                    collision_potential = _get_collisions_with_other_router(
                        other_chip_x, other_chip_y, collision_route,
                        router_tables_by_partition, n_keys_map)

                    collisions[(x, y)][link] = collision_potential

                n_packets = 0  # n_keys_map.n_keys_for_partition(partition)
                collisions[(x, y)][link] += n_packets
    return collisions


def _get_collisions_with_other_router(
        x, y, collision_route, router_tables_by_partition, n_key_map):
    total = 0
    for partition in router_tables_by_partition.get_entries_for_router(x, y):
        entry = router_tables_by_partition.get_entry_on_coords_for_edge(
            partition, x, y)
        if collision_route in entry.link_ids:
            total += n_key_map.n_keys_for_partition(partition)
    return total
