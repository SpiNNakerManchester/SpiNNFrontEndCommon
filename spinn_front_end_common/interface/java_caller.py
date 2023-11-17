# Copyright (c) 2017 The University of Manchester
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

from collections import defaultdict
import json
import logging
import os
import subprocess
from typing import Dict, Tuple, Iterable, List, Optional, cast
from spinn_utilities.config_holder import (
    get_config_str, get_config_str_or_none)
from spinn_utilities.log import FormatAdapter
from spinn_utilities.typing.json import JsonArray, JsonObject
from spinn_machine import Chip
from spinn_machine.tags import IPTag
from pacman.exceptions import PacmanExternalAlgorithmFailedToCompleteException
from pacman.model.graphs import AbstractVirtual
from spinn_front_end_common.data import FecDataView
from pacman.model.placements import Placement
from pacman.model.graphs.application import (
    ApplicationVertex, ApplicationEdgePartition)
from pacman.utilities.algorithm_utilities.routing_algorithm_utilities import (
    vertex_xy, vertex_xy_and_route, get_app_partitions)
from pacman.model.graphs.machine.machine_vertex import MachineVertex
from spinn_front_end_common.utilities.report_functions.write_json_machine \
    import (
        write_json_machine)  # Argh! Mypy
from spinn_front_end_common.utilities.exceptions import (
    ConfigurationException, SpinnFrontEndException)
from spinn_front_end_common.interface.buffer_management.buffer_models import (
    AbstractReceiveBuffersToHost)
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import BufferDatabase

logger = FormatAdapter(logging.getLogger(__name__))


class JavaCaller(object):
    """
    Support class that holds all the stuff for running stuff in Java.
    This includes the work of preparing data for transmitting to Java and
    back.

    This separates the choices of how to call the Java batch vs streaming,
    jar locations, parameters, etc. from the rest of the Python code.
    """
    __slots__ = (
        "_chip_by_ethernet",
        # The call to get java to work. Including the path if required.
        "_java_call",
        # The location of the java jar file
        "_jar_file",
        # The location where the machine json is written
        "_machine_json_path",
        # Dict of chip (x, y) to the p of the monitor vertex
        "_monitor_cores",
        # Flag to indicate if at least one placement is recording
        "_recording",
        # Dict of ethernet (x, y) and the packetGather IPtago
        "_gatherer_iptags",
        # Dict of ethernet (x, y) to the p of the packetGather vertex
        "_gatherer_cores",
        # The location where the latest placement json is written
        "__placement_json",
        # Properties flag to be passed to Java
        "_java_properties")

    def __init__(self) -> None:
        """
        Creates a Java caller and checks the user/configuration parameters.

        :raise ConfigurationException: if simple parameter checking fails.
        """
        self._recording: Optional[bool] = None
        java_call = get_config_str("Java", "java_call")
        self._java_call = java_call
        result = subprocess.call([self._java_call, '-version'])
        if result != 0:
            raise ConfigurationException(
                f" {self._java_call} -version failed. "
                "Please set [Java] java_call to the absolute path "
                "to start java. (in config file)")

        self._find_java_jar()

        self._machine_json_path: Optional[str] = None
        self.__placement_json: Optional[str] = None
        self._monitor_cores: Optional[Dict[Chip, int]] = None
        self._gatherer_iptags: Optional[Dict[Chip, IPTag]] = None
        self._gatherer_cores: Optional[Dict[Chip, int]] = None
        java_properties = get_config_str_or_none("Java", "java_properties")
        self._chip_by_ethernet: Optional[Dict[Chip, List[Chip]]] = None
        if java_properties is not None:
            self._java_properties = java_properties.split()
            # pylint: disable=not-an-iterable
            for _property in self._java_properties:
                if _property[:2] != "-D":
                    raise ConfigurationException(
                        "Java Properties must start with -D "
                        f"found at {_property}")
        else:
            self._java_properties = []

    def _find_java_jar(self) -> None:
        java_spinnaker_path = get_config_str_or_none(
            "Java", "java_spinnaker_path")
        java_jar_path = get_config_str_or_none("Java", "java_jar_path")
        if java_spinnaker_path is None:
            interface = os.path.dirname(os.path.realpath(__file__))
            spinn_front_end_common = os.path.dirname(interface)
            github_checkout_dir = os.path.dirname(spinn_front_end_common)
            parent = os.path.dirname(github_checkout_dir)
            java_spinnaker_path = os.path.join(parent, "JavaSpiNNaker")
        else:
            # As I don't know how to write pwd and /JavaSpiNNaker to one line
            indirect_path = os.path.join(
                java_spinnaker_path, "JavaSpiNNaker")
            if os.path.isdir(indirect_path):
                java_spinnaker_path = indirect_path
        auto_jar_file = os.path.join(
            java_spinnaker_path, "SpiNNaker-front-end",
            "target", "spinnaker-exe.jar")
        if os.path.exists(auto_jar_file):
            if (java_jar_path is None) or (java_jar_path == auto_jar_file):
                self._jar_file = auto_jar_file
            else:
                raise ConfigurationException(
                    f"Found a jar file at {auto_jar_file} "
                    "while java_jar_path as set. "
                    "Please delete on of the two.")
        else:
            if java_jar_path is None:
                if not os.path.isdir(java_spinnaker_path):
                    raise ConfigurationException(
                        f"No Java code found at {java_spinnaker_path} "
                        "nor is java_jar_path set.")
                else:
                    raise ConfigurationException(
                        f"No jar file at {auto_jar_file} "
                        "nor is java_jar_path set.")
            elif os.path.exists(java_jar_path):
                self._jar_file = auto_jar_file
            else:
                raise ConfigurationException(
                    f"No file found at java_jar_path: {java_jar_path}")

    def set_advanced_monitors(self) -> None:
        """
        Create information describing what's going on with the monitor cores.
        """
        tags = FecDataView.get_tags()
        self._monitor_cores = dict()
        for chip, monitor_core in FecDataView.iterate_monitor_items():
            placement = FecDataView.get_placement_of_vertex(monitor_core)
            self._monitor_cores[chip] = placement.p

        self._gatherer_iptags = dict()
        self._gatherer_cores = dict()
        for chip, packet_gather in FecDataView.iterate_gather_items():
            gatherer_tags = tags.get_ip_tags_for_vertex(packet_gather)
            assert gatherer_tags is not None
            self._gatherer_iptags[chip] = gatherer_tags[0]
            placement = FecDataView.get_placement_of_vertex(packet_gather)
            self._gatherer_cores[chip] = placement.p

        self._chip_by_ethernet = defaultdict(list)
        machine = FecDataView.get_machine()
        for chip in machine.chips:
            ethernet = machine[  # pylint: disable=unsubscriptable-object
                chip.nearest_ethernet_x, chip.nearest_ethernet_y]
            self._chip_by_ethernet[ethernet].append(chip)

    def _machine_json(self) -> str:
        """
        Converts the machine in this class to JSON.

        :return: the name of the file containing the JSON
        """
        if self._machine_json_path is None:
            self._machine_json_path = write_json_machine(
                progress_bar=False, validate=False)
        return self._machine_json_path

    def set_placements(self, used_placements: Iterable[Placement]):
        """
        Passes in the placements leaving this class to decide pass it to
        Java.

        Currently the extra information extracted is recording region base
        address but this could change if recording region saved in the
        database.

        Currently this method uses JSON but that may well change to using the
        database.

        :param ~pacman.model.placements.Placements used_placements:
            Placements that are recording. May not be all placements
        """
        path = os.path.join(
            FecDataView.get_json_dir_path(), "java_placements.json")
        self._recording = False
        if self._gatherer_iptags is None:
            self.__placement_json = self._write_recorded_placements(
                used_placements, path)
        else:
            self.__placement_json = self._write_gather(
                used_placements, path)

        # We can write this now too
        self._write_partitions()

    @property
    def _placement_json(self) -> str:
        if self.__placement_json is None:
            raise SpinnFrontEndException("placements not set")
        return self.__placement_json

    def _json_recorded_placement(self, placement: Placement):
        """
        :param ~pacman.model.placements.Placement placement:
        :rtype: dict
        """
        vertex = placement.vertex
        json_placement: JsonObject = {
            "x": placement.x,
            "y": placement.y,
            "p": placement.p,
            "vertex": {
                "label": vertex.label,
                "recordedRegionIds": [],
                "recordingRegionBaseAddress": 0}}

        if isinstance(vertex, AbstractReceiveBuffersToHost) and \
                vertex.get_recorded_region_ids():
            self._recording = True
            json_vertex = cast(JsonObject, json_placement["vertex"])
            # Replace fields in template above
            json_vertex["recordedRegionIds"] = list(
                vertex.get_recorded_region_ids())
            json_vertex["recordingRegionBaseAddress"] = \
                vertex.get_recording_region_base_address(placement)

        return json_placement

    def _json_iptag(self, iptag: IPTag) -> JsonObject:
        """
        :param ~pacman.model.tags.IPTag iptag:
        :rtype: dict
        """
        return {
            "x": iptag.destination_x,
            "y": iptag.destination_y,
            "boardAddress": iptag.board_address,
            "targetAddress": iptag.ip_address,
            # Intentionally not including port!
            "stripSDP": iptag.strip_sdp,
            "tagID": iptag.tag,
            "trafficIdentifier": iptag.traffic_identifier}

    def _json_partition(
            self, partition: ApplicationEdgePartition) -> JsonObject:
        # Partition is:
        # {
        #     # Partition identifier
        #     "identifier": str
        #     # The source vertex label
        #     "label": str
        #     # List of chips containing source machine vertices
        #     "source_chips": [
        #         {
        #             # The coordinates of the source chip.
        #             "x": int, "y": int,
        #             # The labels of machine vertices on the chip.
        #             "machine_vertices": [str]
        #         }, ...
        #     ]
        #     # List of targets by application vertex
        #     "targets": [
        #         {
        #             # Target application vertex name
        #             "target_app_vertex": str (label of vertex),
        #             # Target machine vertices and sources which target them
        #             "target_m_vertices": [
        #                 {
        #                     # Chip of the target
        #                     "x": int, "y": int,
        #                     # Core or link of the target (might be virtual)
        #                     "p": int or null
        #                     "l": int or null
        #                     # List of source vertex labels to target this
        #                     "sources": [
        #                         {
        #                             "is_app_vertex": bool.
        #                             "label": str,
        #                             "app_vertex_label": str
        #                         }, ...
        #                     ]
        #                 }, ...
        #             ]
        #         }, ...
        #     ]
        # }
        json_dict: JsonObject = dict()
        json_dict["identifier"] = partition.identifier
        json_dict["label"] = partition.pre_vertex.label
        outgoing: Dict[Tuple[int, int], JsonArray] = defaultdict(list)
        pre_splitter = partition.pre_vertex.splitter
        for pre_m_vertex in pre_splitter.get_out_going_vertices(
                partition.identifier):
            x, y = vertex_xy(pre_m_vertex)
            outgoing[(x, y)].append(pre_m_vertex.label)
        outgoing_list: JsonArray = []
        for (x, y), sources in outgoing.items():
            outgoing_list.append({"x": x, "y": y, "machine_vertices": sources})
        json_dict["source_chips"] = outgoing_list

        targets: JsonArray = []
        for edge in partition.edges:
            sp = edge.post_vertex.splitter
            target_dict: JsonObject = dict()
            target_dict["target_app_vertex"] = edge.post_vertex.label
            target_m_vertices: JsonArray = list()
            for m_vertex, srcs in sp.get_source_specific_in_coming_vertices(
                    partition.pre_vertex, partition.identifier):
                (x, y), (_, p, l) = vertex_xy_and_route(m_vertex)
                target_m_vertex: JsonObject = {"x": x, "y": y, "p": p, "l": l}
                source_list: JsonArray = list()
                for source in srcs:
                    is_app_vtx = isinstance(source, ApplicationVertex)
                    source_dict: JsonObject = dict()
                    source_dict["is_app_vertex"] = is_app_vtx
                    source_dict["label"] = source.label
                    if is_app_vtx:
                        source_dict["app_vertex_label"] = source.label
                    else:
                        source_dict["app_vertex_label"] = \
                            source.app_vertex.label
                    source_list.append(source_dict)
                target_m_vertex["sources"] = source_list
                target_m_vertices.append(target_m_vertex)
            target_dict["target_m_vertices"] = target_m_vertices
            targets.append(target_dict)

        internal_parts = pre_splitter.get_internal_multicast_partitions()
        if internal_parts:
            # Gather the internal sources for each target
            internal_targets: Dict[MachineVertex, JsonArray] = \
                defaultdict(list)
            for in_part in internal_parts:
                src = in_part.pre_vertex
                for edge in in_part.edges:
                    tgt = edge.post_vertex
                    internal_targets[tgt].append(
                        {"is_app_vertex": False, "label": src.label or "",
                         "app_vertex_label": partition.pre_vertex.label or ""})

            int_target_dict: JsonObject = dict()
            int_target_dict["target_app_vertex"] = partition.pre_vertex.label
            int_target_m_vertices: JsonArray = list()
            for int_tgt, int_srcs in internal_targets.items():
                (i_x, i_y), (_, i_p, i_l) = vertex_xy_and_route(int_tgt)
                int_target_m_vertices.append(
                    {"x": i_x, "y": i_y, "p": i_p, "l": i_l,
                     "sources": int_srcs})
            int_target_dict["target_m_vertices"] = int_target_m_vertices
            targets.append(int_target_dict)

        json_dict["targets"] = targets
        return json_dict

    def _placements_grouped(
            self, recording_placements: Iterable[Placement]) -> Dict[
                Chip, Dict[Chip, List[Placement]]]:
        """
        :param ~pacman.model.placements.Placements recording_placementss:
        :rtype: dict(Chip,dict(Chip,~pacman.model.placements.Placement))
        """
        by_ethernet: Dict[Chip, Dict[Chip, List[Placement]]] = defaultdict(
            lambda: defaultdict(list))
        machine = FecDataView.get_machine()
        for placement in recording_placements:
            if not isinstance(placement.vertex, AbstractVirtual):
                chip = placement.chip
                ethernet = machine.get_chip_at(
                    chip.nearest_ethernet_x, chip.nearest_ethernet_y)
                if ethernet:
                    by_ethernet[ethernet][chip].append(placement)
        return by_ethernet

    def _write_gather(
            self, used_placements: Iterable[Placement], path: str) -> str:
        """
        :param ~pacman.model.placements.Placements used_placements:
            placements that are being used. May not be all placements
        :param str path:
        :rtype: str
        """
        assert self._chip_by_ethernet is not None
        assert self._gatherer_cores is not None
        assert self._gatherer_iptags is not None
        assert self._monitor_cores is not None

        placements_by_ethernet = self._placements_grouped(used_placements)
        json_obj: JsonArray = list()
        for ethernet in self._chip_by_ethernet:
            by_chip = placements_by_ethernet[ethernet]
            json_gather: JsonObject = {
                "x": ethernet.x,
                "y": ethernet.y,
                "p": self._gatherer_cores[ethernet],
                "iptag": self._json_iptag(self._gatherer_iptags[ethernet])}
            json_chips: JsonArray = list()
            for chip in self._chip_by_ethernet[ethernet]:
                json_chip: JsonObject = {
                    "x": chip.x,
                    "y": chip.y,
                    "p": self._monitor_cores[chip]}
                if chip in by_chip:
                    json_placements = [
                        self._json_recorded_placement(placement)
                        for placement in by_chip[chip]]
                    if json_placements:
                        json_chip["placements"] = json_placements
                json_chips.append(json_chip)
            json_gather["monitors"] = json_chips
            json_obj.append(json_gather)

        # dump to json file
        with open(path, "w", encoding="utf-8") as f:
            json.dump(json_obj, f)

        return path

    def _write_recorded_placements(
            self, used_placements: Iterable[Placement], path: str) -> str:
        """
        :param ~pacman.model.placements.Placements placements:
            Placements that are being used. May not be all placements
        :param str path:
        :rtype: str
        """
        # Read back the regions
        json_obj: JsonArray = list()
        for placement in used_placements:
            if not isinstance(placement.vertex, AbstractVirtual):
                json_p = self._json_recorded_placement(placement)
                if json_p:
                    json_obj.append(json_p)

        # dump to json file
        with open(path, "w", encoding="utf-8") as f:
            json.dump(json_obj, f)

        return path

    def _write_partitions(self) -> None:
        path: str = os.path.join(
            FecDataView.get_json_dir_path(), "java_partitions.json")
        json_obj: JsonArray = list()
        for partition in get_app_partitions():
            json_obj.append(self._json_partition(partition))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(json_obj, f)

    def _run_java(self, *args: str) -> int:
        """
        Does the actual running of `JavaSpiNNaker`. Arguments are those that
        will be processed by the `main` method on the Java side.

        :type list(str) args:
        :rtype: int
        """
        if self._java_properties is None:
            params = [self._java_call, '-jar', self._jar_file]
        else:
            params = [self._java_call] + self._java_properties \
                     + ['-jar', self._jar_file]
        params.extend(args)
        return subprocess.call(params)

    def get_all_data(self) -> None:
        """
        Gets all the data from the previously set placements
        and put these in the previously set database.

        :raises PacmanExternalAlgorithmFailedToCompleteException:
            On failure of the Java code.
        """
        if not self._recording:
            return

        if self._gatherer_iptags is None:
            result = self._run_java(
                'download', self._placement_json, self._machine_json(),
                BufferDatabase.default_database_file(),
                FecDataView.get_run_dir_path())
        else:
            result = self._run_java(
                'gather', self._placement_json, self._machine_json(),
                BufferDatabase.default_database_file(),
                FecDataView.get_run_dir_path())
        if result != 0:
            log_file = os.path.join(
                FecDataView.get_run_dir_path(), "jspin.log")
            raise PacmanExternalAlgorithmFailedToCompleteException(
                "Java call exited with value " + str(result) + " see "
                + str(log_file) + " for logged info")

    def load_system_data_specification(self) -> None:
        """
        Writes all the data specifications for system cores,
        uploading the result to the machine.

        :raises PacmanExternalAlgorithmFailedToCompleteException:
            On failure of the Java code.
        """
        result = self._run_java(
            'dse_sys', self._machine_json(),
            FecDataView.get_ds_database_path(),
            FecDataView.get_run_dir_path())
        if result != 0:
            log_file = os.path.join(
                FecDataView.get_run_dir_path(), "jspin.log")
            raise PacmanExternalAlgorithmFailedToCompleteException(
                "Java call exited with value " + str(result) + " see "
                + str(log_file) + " for logged info")

    def load_app_data_specification(self, use_monitors: bool) -> None:
        """
        Writes all the data specifications for application cores,
        uploading the result to the machine.

        .. note::
            May assume that system cores are already loaded and running if
            `use_monitors` is set to `True`.

        :param bool use_monitors:
        :raises PacmanExternalAlgorithmFailedToCompleteException:
            On failure of the Java code.
        """
        if use_monitors:
            result = self._run_java(
                'dse_app_mon', self._placement_json, self._machine_json(),
                FecDataView.get_ds_database_path(),
                FecDataView.get_run_dir_path())
        else:
            result = self._run_java(
                'dse_app', self._machine_json(),
                FecDataView.get_ds_database_path(),
                FecDataView.get_run_dir_path())
        if result != 0:
            log_file = os.path.join(
                FecDataView.get_run_dir_path(), "jspin.log")
            raise PacmanExternalAlgorithmFailedToCompleteException(
                "Java call exited with value " + str(result) + " see "
                + str(log_file) + " for logged info")
