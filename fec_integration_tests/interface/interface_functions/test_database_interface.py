# Copyright (c) 2022 The University of Manchester
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
from typing import Iterable, Sequence

from spinn_utilities.config_holder import set_config
from spinn_utilities.overrides import overrides

from spinn_machine.version.version_strings import VersionStrings
from spinn_machine.tags.iptag import IPTag

from pacman.model.graphs.application import ApplicationVertex, ApplicationEdge
from pacman.model.graphs.machine import MachineVertex, SimpleMachineVertex
from pacman.model.resources import ConstantSDRAM
from pacman.model.placements import Placements, Placement
from pacman.model.routing_info import (
    RoutingInfo, MachineVertexRoutingInfo, AppVertexRoutingInfo)
from pacman.model.routing_info.base_key_and_mask import BaseKeyAndMask
from pacman.model.tags.tags import Tags
from pacman.model.partitioner_splitters import AbstractSplitterCommon
from pacman.model.graphs.common.slice import Slice
from pacman.utilities.utility_objs import ChipCounter

from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.interface_functions import (
    database_interface)

from spinn_front_end_common.utilities.utility_objs import (
    LivePacketGatherParameters)
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utility_models import LivePacketGather
from spinn_front_end_common.utilities.database import DatabaseReader


class MockSplitter(AbstractSplitterCommon):

    @overrides(AbstractSplitterCommon.create_machine_vertices)
    def create_machine_vertices(self, chip_counter: ChipCounter) -> None:
        pass

    @overrides(AbstractSplitterCommon.get_out_going_slices)
    def get_out_going_slices(self) -> Sequence[Slice]:
        raise NotImplementedError()

    @overrides(AbstractSplitterCommon.get_in_coming_slices)
    def get_in_coming_slices(self) -> Sequence[Slice]:
        raise NotImplementedError()

    @overrides(AbstractSplitterCommon.get_out_going_vertices)
    def get_out_going_vertices(
            self, partition_id: str) -> Sequence[MachineVertex]:
        return self.governed_app_vertex.machine_vertices

    @overrides(AbstractSplitterCommon.get_in_coming_vertices)
    def get_in_coming_vertices(
            self, partition_id: str) -> Sequence[MachineVertex]:
        raise NotImplementedError()

    @overrides(AbstractSplitterCommon.machine_vertices_for_recording)
    def machine_vertices_for_recording(
            self, variable_to_record: str) -> Iterable[MachineVertex]:
        raise NotImplementedError()

    @overrides(AbstractSplitterCommon.reset_called)
    def reset_called(self) -> None:
        pass


class MockAppVertex(ApplicationVertex):
    def __init__(self, n_atoms, label):
        super(MockAppVertex, self).__init__(
            label=label, splitter=MockSplitter())
        self.__n_atoms = n_atoms

    @property
    def n_atoms(self) -> int:
        return self.__n_atoms


def _make_m_vertices(app_vertex, n_m_vertices, atoms_per_core):
    for i in range(n_m_vertices):
        m_vertex = SimpleMachineVertex(
            ConstantSDRAM(0), label=f"{app_vertex.label}_{i}",
            vertex_slice=Slice(
                i * atoms_per_core, ((i + 1) * atoms_per_core) - 1),
            app_vertex=app_vertex)
        app_vertex.remember_machine_vertex(m_vertex)


def _add_rinfo(
        app_vertex, partition_id, routing_info, base_key, app_mask, mac_mask,
        m_vertex_shift):
    routing_info.add_routing_info(AppVertexRoutingInfo(
        BaseKeyAndMask(base_key, app_mask), partition_id, app_vertex,
        mac_mask, 1, 1))
    for i, m_vertex in enumerate(app_vertex.machine_vertices):
        routing_info.add_routing_info(MachineVertexRoutingInfo(
            BaseKeyAndMask(
                base_key | i << m_vertex_shift, app_mask | mac_mask),
            partition_id, m_vertex, i))


def _place_vertices(app_vertexes, placements):
    machine = FecDataView.get_machine()
    chips = machine.chips
    chip = next(chips)
    x, y = chip
    placable_processors_ids = chip.placable_processors_ids
    i = 0
    for app_vertex in app_vertexes:
        for m_vertex in app_vertex.machine_vertices:
            while placements.is_processor_occupied(
                    x, y, placable_processors_ids[i]):
                i += 1
                if i >= len(placable_processors_ids):
                    chip = next(chips)
                    x, y = chip
                    placable_processors_ids = chip.placable_processors_ids
                    i = 0
            placements.add_placement(
                Placement(m_vertex, x, y, placable_processors_ids[i]))
    return placements


def test_database_interface():
    unittest_setup()
    set_config("Machine", "versions", VersionStrings.ANY.text)
    set_config("Database", "create_database", "True")
    set_config("Database", "create_routing_info_to_neuron_id_mapping", "True")

    writer = FecDataWriter.mock()
    placements = Placements()

    app_vertex_1 = MockAppVertex(100, "test_1")
    app_vertex_2 = MockAppVertex(200, "test_2")
    writer.add_vertex(app_vertex_1)
    writer.add_vertex(app_vertex_2)
    writer.add_edge(ApplicationEdge(app_vertex_1, app_vertex_2), "Test")

    _make_m_vertices(app_vertex_1, 10, 10)
    _make_m_vertices(app_vertex_2, 20, 20)
    params = LivePacketGatherParameters(
        label="LiveSpikeReceiver", port=10000, hostname="localhost")
    lpg_vertex = LivePacketGather(params, label="LiveSpikeReceiver")
    writer.add_vertex(lpg_vertex)
    writer.add_edge(ApplicationEdge(app_vertex_1, lpg_vertex), "Test")

    lpg_vertex.splitter.create_sys_vertices(placements)

    _place_vertices([app_vertex_1, app_vertex_2], placements)

    writer.set_placements(placements)
    lpg_vertex.splitter.get_source_specific_in_coming_vertices(
        app_vertex_1, "Test")

    routing_info = RoutingInfo()
    _add_rinfo(
        app_vertex_1, "Test", routing_info,
        0x10000000, 0xFFFF0000, 0x0000FF00, 8)
    _add_rinfo(
        app_vertex_2, "Test", routing_info,
        0x20000000, 0xFFFF0000, 0x0000FF00, 8)
    writer.set_routing_infos(routing_info)

    tags = Tags()
    tag = IPTag("127.0.0.1", 0, 0, 1, "127.0.0.1", 12345, True)
    tags.add_ip_tag(tag, next(iter(lpg_vertex.machine_vertices)))
    writer.set_tags(tags)

    db_path = database_interface(1000)
    print(db_path)

    with DatabaseReader(db_path) as reader:
        assert (reader.get_ip_address(0, 0) ==
                writer.get_chip_at(0, 0).ip_address)
        assert all(db_p ==
                   placements.get_placement_of_vertex(m_vertex).location
                   for db_p, m_vertex in zip(
                       reader.get_placements(app_vertex_1.label),
                       app_vertex_1.machine_vertices))
        assert reader.get_configuration_parameter_value("runtime") == 1000
        assert (
            reader.get_live_output_details(
                app_vertex_1.label, lpg_vertex.label) ==
            (tag.ip_address, tag.port, tag.strip_sdp, tag.board_address,
             tag.tag, tag.destination_x, tag.destination_y))
        assert reader.get_atom_id_to_key_mapping(app_vertex_1.label)
        assert reader.get_key_to_atom_id_mapping(app_vertex_1.label)
