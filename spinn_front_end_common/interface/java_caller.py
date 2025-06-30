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
import datetime
from io import BufferedReader
import json
import logging
import os
import subprocess
import selectors
import sys
from typing import Dict, Iterable, List, Optional, cast

from spinn_utilities.config_holder import (
    get_config_str, get_config_str_or_none, get_report_path)
from spinn_utilities.log import FormatAdapter
from spinn_utilities.typing.json import JsonArray, JsonObject
from spinn_machine import Chip
from spinn_machine.tags import IPTag
from pacman.model.graphs import AbstractVirtual
from pacman.model.placements import Placement

from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.report_functions.write_json_machine \
    import write_json_machine
from spinn_front_end_common.utilities.exceptions import (
    ConfigurationException, SpinnFrontEndException)
from spinn_front_end_common.interface.buffer_management.buffer_models import (
    AbstractReceiveBuffersToHost, AbstractReceiveRegionsToHost)
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
        # The call to get Java to work. Including the path if required.
        "_java_call",
        # The location of the Java jar file
        "_jar_file",
        # The location where the machine json is written
        "_machine_json_path",
        # Dict of chip (x, y) to the p of the monitor vertex
        "_monitor_cores",
        # Flag to indicate if at least one placement is recording
        "_recording",
        # Dict of Ethernet (x, y) and the packetGather IPtags
        "_gatherer_iptags",
        # Dict of Ethernet (x, y) to the p of the packetGather vertex
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
            # As I don't know how to write this to one line
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
                self._jar_file = java_jar_path
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
            ethernet = machine[
                chip.nearest_ethernet_x, chip.nearest_ethernet_y]
            self._chip_by_ethernet[ethernet].append(chip)

    def _machine_json(self) -> str:
        """
        Converts the machine in this class to JSON.

        :return: the name of the file containing the JSON
        """
        if self._machine_json_path is None:
            self._machine_json_path = write_json_machine(progress_bar=False)
        return self._machine_json_path

    def set_placements(self, used_placements: Iterable[Placement]) -> None:
        """
        Passes in the placements leaving this class to decide pass it to
        Java.

        Currently the extra information extracted is recording region base
        address but this could change if recording region saved in the
        database.

        Currently this method uses JSON but that may well change to using the
        database.

        :param used_placements:
            Placements that are recording. May not be all placements
        """
        path = get_report_path(
            section="Java", option="path_json_java_placements")
        self._recording = False
        if self._gatherer_iptags is None:
            self.__placement_json = self._write_placements(
                used_placements, path)
        else:
            self.__placement_json = self._write_gather(
                used_placements, path)

    @property
    def _placement_json(self) -> str:
        if self.__placement_json is None:
            raise SpinnFrontEndException("placements not set")
        return self.__placement_json

    def _json_placement(self, placement: Placement) -> JsonObject:
        vertex = placement.vertex
        json_placement: JsonObject = {
            "x": placement.x,
            "y": placement.y,
            "p": placement.p,
            "vertex": {
                "label": vertex.label,
                "recordedRegionIds": [],
                "recordingRegionBaseAddress": 0,
                "downloadRegions": []}}

        if isinstance(vertex, AbstractReceiveBuffersToHost):
            recording_regions = cast(
                JsonArray, list(vertex.get_recorded_region_ids()))
            if recording_regions:
                self._recording = True
                json_vertex = cast(JsonObject, json_placement["vertex"])
                # Replace fields in template above
                json_vertex["recordedRegionIds"] = recording_regions
                json_vertex["recordingRegionBaseAddress"] = \
                    vertex.get_recording_region_base_address(placement)
        if isinstance(vertex, AbstractReceiveRegionsToHost):
            download_regions = list(vertex.get_download_regions(placement))
            if download_regions:
                self._recording = True
                json_vertex = cast(JsonObject, json_placement["vertex"])
                json_vertex["downloadRegions"] = [
                    {"index": region_id, "address": address, "size": size}
                    for region_id, address, size in download_regions]

        return json_placement

    def _json_iptag(self, iptag: IPTag) -> JsonObject:
        return {
            "x": iptag.destination_x,
            "y": iptag.destination_y,
            "boardAddress": iptag.board_address,
            "targetAddress": iptag.ip_address,
            # Intentionally not including port!
            "stripSDP": iptag.strip_sdp,
            "tagID": iptag.tag,
            "trafficIdentifier": iptag.traffic_identifier}

    def _placements_grouped(
            self, recording_placements: Iterable[Placement]) -> Dict[
                Chip, Dict[Chip, List[Placement]]]:
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
        :param used_placements:
            placements that are being used. May not be all placements
        :param path:
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
                    json_placements: JsonArray = [
                        self._json_placement(placement)
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

    def _write_placements(
            self, used_placements: Iterable[Placement], path: str) -> str:
        """
        :param used_placements:
            Placements that are being used. May not be all placements
        :param path:
        """
        # Read back the regions
        json_obj: JsonArray = list()
        for placement in used_placements:
            if not isinstance(placement.vertex, AbstractVirtual):
                json_p = self._json_placement(placement)
                if json_p:
                    json_obj.append(json_p)

        # dump to json file
        with open(path, "w", encoding="utf-8") as f:
            json.dump(json_obj, f)

        return path

    def _run_java(self, *args: str) -> None:
        """
        Does the actual running of `JavaSpiNNaker`. Arguments are those that
        will be processed by the `main` method on the Java side.
        """
        if self._java_properties is None:
            params = [self._java_call, '-jar', self._jar_file]
        else:
            params = [self._java_call] + self._java_properties \
                     + ['-jar', self._jar_file]
        params.extend(args)
        logger.info("Calling Java with: {}", " ".join(params))

        with subprocess.Popen(params, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) as process:
            sel = selectors.DefaultSelector()
            sel.register(cast(int, process.stdout), selectors.EVENT_READ)
            sel.register(cast(int, process.stderr), selectors.EVENT_READ)

            all_output = ""
            while process.poll() is None:
                for key, _ in sel.select():
                    data = cast(BufferedReader, key.fileobj).read1().decode()
                    if not data:
                        break
                    if key.fileobj is process.stdout:
                        all_output += data
                        print(data, end="")
                    else:
                        all_output += data
                        print(data, end="", file=sys.stderr)
            if process.returncode != 0:
                logger.error("Java Call resulted in an error")
                updated = datetime.datetime.fromtimestamp(
                    os.path.getmtime(self._jar_file))
                updated_str = (
                    f"{updated.year:04}-{updated.month:02}-{updated.day:02}"
                    f"-{updated.hour:02}-{updated.minute:02}")
                logger.error(f"Jar {self._jar_file} was updated {updated_str}")
                logger.error(f"Call was {params}")
                logger.error("Output was:")
                logger.error(all_output)
                log_file = get_report_path("path_java_log")
                logger.error(f"Logging to: {log_file}")
                raise subprocess.CalledProcessError(
                    process.returncode, params, output=all_output)

    def extract_all_data(self) -> None:
        """
        Gets all the data from the previously set placements
        and put these in the previously set database.

        :raises subprocess.CalledProcessError
            On failure of the Java code.
        """
        if not self._recording:
            return

        if self._gatherer_iptags is None:
            self._run_java(
                'download', self._placement_json, self._machine_json(),
                BufferDatabase.default_database_file(),
                get_report_path("path_java_log"))
        else:
            self._run_java(
                'gather', self._placement_json, self._machine_json(),
                BufferDatabase.default_database_file(),
                get_report_path("path_java_log"))

    def load_system_data_specification(self) -> None:
        """
        Writes all the data specifications for system cores,
        uploading the result to the machine.

        :raises subprocess.CalledProcessError:
            On failure of the Java code.
        """
        self._run_java(
            'dse_sys', self._machine_json(),
            FecDataView.get_ds_database_path(),
            get_report_path("path_java_log"))

    def load_app_data_specification(self, use_monitors: bool) -> None:
        """
        Writes all the data specifications for application cores,
        uploading the result to the machine.

        .. note::
            May assume that system cores are already loaded and running if
            `use_monitors` is set to `True`.

        :param use_monitors:
        :raises subprocess.CalledProcessError:
            On failure of the Java code.
        """
        if use_monitors:
            self._run_java(
                'dse_app_mon', self._placement_json, self._machine_json(),
                FecDataView.get_ds_database_path(),
                get_report_path("path_java_log"))
        else:
            self._run_java(
                'dse_app', self._machine_json(),
                FecDataView.get_ds_database_path(),
                get_report_path("path_java_log"))
