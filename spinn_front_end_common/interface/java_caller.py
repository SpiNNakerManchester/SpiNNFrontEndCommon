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
from spinn_utilities.config_holder import get_config_str
from spinn_utilities.log import FormatAdapter
from pacman.exceptions import PacmanExternalAlgorithmFailedToCompleteException
from pacman.model.graphs import AbstractVirtual
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.report_functions import (
    write_json_machine)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.interface.buffer_management.buffer_models import (
    AbstractReceiveBuffersToHost)
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import BufferDatabase
from spinn_front_end_common.interface.ds import DsSqlliteDatabase

logger = FormatAdapter(logging.getLogger(__name__))


class JavaCaller(object):
    """
    Support class that holds all the stuff for running stuff in Java.
    This includes the work of preparing data for transmitting to Java and
    back.

    This separates the choices of how to call the Java batch vs streaming,
    jar locations, parameters, etc. from the rest of the Python code.
    """

    __slots__ = [
        "_chipxy_by_ethernet",
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
        "_placement_json",
        # Properties flag to be passed to Java
        "_java_properties"
    ]

    def __init__(self):
        """
        Creates a Java caller and checks the user/configuration parameters.

        :raise ConfigurationException: if simple parameter checking fails.
        """
        self._recording = None
        self._java_call = get_config_str("Java", "java_call")
        result = subprocess.call([self._java_call, '-version'])
        if result != 0:
            raise ConfigurationException(
                f" {self._java_call} -version failed. "
                "Please set [Java] java_call to the absolute path "
                "to start java. (in config file)")

        self._find_java_jar()

        self._machine_json_path = None
        self._placement_json = None
        self._monitor_cores = None
        self._gatherer_iptags = None
        self._gatherer_cores = None
        self._java_properties = get_config_str("Java", "java_properties")
        self._chipxy_by_ethernet = None
        if self._java_properties is not None:
            self._java_properties = self._java_properties.split()
            # pylint: disable=not-an-iterable
            for _property in self._java_properties:
                if _property[:2] != "-D":
                    raise ConfigurationException(
                        "Java Properties must start with -D "
                        f"found at {_property}")

    def _find_java_jar(self):
        java_spinnaker_path = get_config_str("Java", "java_spinnaker_path")
        java_jar_path = get_config_str("Java", "java_jar_path")
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

    def set_advanced_monitors(self):
        """
        Create information describing what's going on with the monitor cores.
        """
        tags = FecDataView.get_tags()
        self._monitor_cores = dict()
        for core, monitor_core in FecDataView.iterate_monitor_items():
            placement = FecDataView.get_placement_of_vertex(monitor_core)
            self._monitor_cores[core] = placement.p

        self._gatherer_iptags = dict()
        self._gatherer_cores = dict()
        for core, packet_gather in FecDataView.iterate_gather_items():
            self._gatherer_iptags[core] = \
                tags.get_ip_tags_for_vertex(packet_gather)[0]
            placement = FecDataView.get_placement_of_vertex(packet_gather)
            self._gatherer_cores[core] = placement.p

        self._chipxy_by_ethernet = defaultdict(list)
        machine = FecDataView.get_machine()
        for chip in machine.chips:
            chip_xy = (chip.x, chip.y)
            ethernet = (chip.nearest_ethernet_x, chip.nearest_ethernet_y)
            self._chipxy_by_ethernet[ethernet].append(chip_xy)

    def _machine_json(self):
        """
        Converts the machine in this class to JSON.

        :return: the name of the file containing the JSON
        """
        if self._machine_json_path is None:
            self._machine_json_path = write_json_machine(
                progress_bar=False, validate=False)
        return self._machine_json_path

    def set_placements(self, used_placements):
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
            self._placement_json = self._write_placements(
                used_placements, path)
        else:
            self._placement_json = self._write_gather(
                used_placements, path)

    def _json_placement(self, placement):
        """
        :param ~pacman.model.placements.Placement placement:
        :rtype: dict
        """
        vertex = placement.vertex
        json_placement = dict()
        json_placement["x"] = placement.x
        json_placement["y"] = placement.y
        json_placement["p"] = placement.p

        json_vertex = dict()
        json_vertex["label"] = vertex.label
        if isinstance(vertex, AbstractReceiveBuffersToHost) and \
                vertex.get_recorded_region_ids():
            self._recording = True
            json_vertex["recordedRegionIds"] = vertex.get_recorded_region_ids()
            json_vertex["recordingRegionBaseAddress"] = \
                vertex.get_recording_region_base_address(placement)
        else:
            json_vertex["recordedRegionIds"] = []
            json_vertex["recordingRegionBaseAddress"] = 0
        json_placement["vertex"] = json_vertex

        return json_placement

    def _json_iptag(self, iptag):
        """
        :param ~pacman.model.tags.IPTag iptag:
        :rtype: dict
        """
        json_tag = dict()
        json_tag["x"] = iptag.destination_x
        json_tag["y"] = iptag.destination_y
        json_tag["boardAddress"] = iptag.board_address
        json_tag["targetAddress"] = iptag.ip_address
        # Intentionally not including port!
        json_tag["stripSDP"] = iptag.strip_sdp
        json_tag["tagID"] = iptag.tag
        json_tag["trafficIdentifier"] = iptag.traffic_identifier

        return json_tag

    def _placements_grouped(self, recording_placements):
        """
        :param ~pacman.model.placements.Placements recording_placementss:
        :rtype: dict(tuple(int,int),dict(tuple(int,int),
            ~pacman.model.placements.Placement))
        """
        by_ethernet = defaultdict(lambda: defaultdict(list))
        for placement in recording_placements:
            if not isinstance(placement.vertex, AbstractVirtual):
                machine = FecDataView.get_machine()
                chip = machine.get_chip_at(placement.x, placement.y)
                chip_xy = (placement.x, placement.y)
                ethernet = (chip.nearest_ethernet_x, chip.nearest_ethernet_y)
                by_ethernet[ethernet][chip_xy].append(placement)
        return by_ethernet

    def _write_gather(self, used_placements, path):
        """
        :param ~pacman.model.placements.Placements used_placements:
            placements that are being used. May not be all placements
        :param str path:
        :rtype: str
        """
        placements_by_ethernet = self._placements_grouped(used_placements)
        json_obj = list()
        for ethernet in self._chipxy_by_ethernet:
            by_chip = placements_by_ethernet[ethernet]
            json_gather = dict()
            json_gather["x"] = ethernet[0]
            json_gather["y"] = ethernet[1]
            json_gather["p"] = self._gatherer_cores[ethernet]
            json_gather["iptag"] = self._json_iptag(
                self._gatherer_iptags[ethernet])
            json_chips = list()
            for chip_xy in self._chipxy_by_ethernet[ethernet]:
                json_chip = dict()
                json_chip["x"] = chip_xy[0]
                json_chip["y"] = chip_xy[1]
                json_chip["p"] = self._monitor_cores[chip_xy]
                if chip_xy in by_chip:
                    json_placements = list()
                    for placement in by_chip[chip_xy]:
                        json_p = self._json_placement(placement)
                        if json_p:
                            json_placements.append(json_p)
                    if len(json_placements) > 0:
                        json_chip["placements"] = json_placements
                json_chips.append(json_chip)
            json_gather["monitors"] = json_chips
            json_obj.append(json_gather)

        # dump to json file
        with open(path, "w", encoding="utf-8") as f:
            json.dump(json_obj, f)

        return path

    def _write_placements(self, used_placements, path):
        """
        :param ~pacman.model.placements.Placements placements:
            Placements that are being used. May not be all placements
        :param str path:
        :rtype: str
        """
        # Read back the regions
        json_obj = list()
        for placement in used_placements:
            if not isinstance(placement.vertex, AbstractVirtual):
                json_p = self._json_placement(placement)
                if json_p:
                    json_obj.append(json_p)

        # dump to json file
        with open(path, "w", encoding="utf-8") as f:
            json.dump(json_obj, f)

        return path

    def _run_java(self, *args):
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

    def get_all_data(self):
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

    def execute_data_specification(self):
        """
        Writes all the data specifications, uploading the result to the
        machine.

        :raises PacmanExternalAlgorithmFailedToCompleteException:
            On failure of the Java code.
        """
        result = self._run_java(
            'dse', self._machine_json(),
            DsSqlliteDatabase.default_database_file(),
            FecDataView.get_run_dir_path())
        if result != 0:
            log_file = os.path.join(
                FecDataView.get_run_dir_path(), "jspin.log")
            raise PacmanExternalAlgorithmFailedToCompleteException(
                "Java call exited with value " + str(result) + " see "
                + str(log_file) + " for logged info")

    def execute_system_data_specification(self):
        """
        Writes all the data specifications for system cores,
        uploading the result to the machine.

        :raises PacmanExternalAlgorithmFailedToCompleteException:
            On failure of the Java code.
        """
        result = self._run_java(
            'dse_sys', self._machine_json(),
            DsSqlliteDatabase.default_database_file(),
            FecDataView.get_run_dir_path())
        if result != 0:
            log_file = os.path.join(
                FecDataView.get_run_dir_path(), "jspin.log")
            raise PacmanExternalAlgorithmFailedToCompleteException(
                "Java call exited with value " + str(result) + " see "
                + str(log_file) + " for logged info")

    def execute_app_data_specification(self, use_monitors):
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
                DsSqlliteDatabase.default_database_file(),
                FecDataView.get_run_dir_path())
        else:
            result = self._run_java(
                'dse_app', self._machine_json(),
                DsSqlliteDatabase.default_database_file(),
                FecDataView.get_run_dir_path())
        if result != 0:
            log_file = os.path.join(
                FecDataView.get_run_dir_path(), "jspin.log")
            raise PacmanExternalAlgorithmFailedToCompleteException(
                "Java call exited with value " + str(result) + " see "
                + str(log_file) + " for logged info")
