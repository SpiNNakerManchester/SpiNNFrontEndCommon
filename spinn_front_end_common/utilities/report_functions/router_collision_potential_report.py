# Copyright (c) 2019-2020 The University of Manchester
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

import os
from collections import defaultdict
from spinn_machine.router import Router
from spinn_front_end_common.data import FecDataView

COLLISION_REPORT = "routing_collision_protential_report.rpt"


def router_collision_potential_report():
    file_name = os.path.join(
        FecDataView.get_run_dir_path(),
        "routing_collision_protential_report.rpt")
    with open(file_name, "w") as writer:
        collision_counts = _generate_data()
        _write_report(collision_counts, writer)


def _write_report(collision_counts, writer):
    if len(collision_counts) == 0:
        writer.write("There are no collisions in this network mapping")
        return

    for (x, y) in collision_counts:
        for link_id in collision_counts[(x, y)]:
            writer.write(
                "router {}:{} link {} has potential {} collisions "
                "\n".format(
                    x, y, link_id, collision_counts[(x, y)][link_id]))


def _generate_data():
    router_tables_by_partition = FecDataView.get_routing_table_by_partition()
    collisions = defaultdict(lambda: defaultdict(int))
    n_keys_map = FecDataView.get_machine_partition_n_keys_map()
    for (x, y) in router_tables_by_partition.get_routers():
        for partition in \
                router_tables_by_partition.get_entries_for_router(x, y):
            entry = \
                router_tables_by_partition.get_entry_on_coords_for_edge(
                    partition, x, y)
            for link in entry.link_ids:
                if collisions[(x, y)][link] == 0:
                    chip = FecDataView.get_chip_at(x, y)
                    other_chip_x = chip.router.get_link(link).destination_x
                    other_chip_y = chip.router.get_link(link).destination_y
                    collision_route = Router.opposite(link)

                    collision_potential = \
                        _get_collisions_with_other_router(
                            other_chip_x, other_chip_y, collision_route,
                            router_tables_by_partition, n_keys_map)

                    collisions[(x, y)][link] = collision_potential

                n_packets = n_keys_map.n_keys_for_partition(partition)
                collisions[(x, y)][link] += n_packets
    return collisions


def _get_collisions_with_other_router(
        x, y, collision_route, router_tables_by_partition, n_key_map):
    total = 0
    for partition in \
            router_tables_by_partition.get_entries_for_router(x, y):
        entry = router_tables_by_partition.get_entry_on_coords_for_edge(
            partition, x, y)
        if collision_route in entry.link_ids:
            total += n_key_map.n_keys_for_partition(partition)
    return total
