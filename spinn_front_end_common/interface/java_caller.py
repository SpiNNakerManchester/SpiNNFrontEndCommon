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

from collections import defaultdict, OrderedDict
import json
import logging
import os
import subprocess
from spinn_utilities.log import FormatAdapter
from pacman.exceptions import PacmanExternalAlgorithmFailedToCompleteException
from pacman.utilities.file_format_converters.convert_to_java_machine import (
    ConvertToJavaMachine)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.interface.buffer_management.buffer_models import (
    AbstractReceiveBuffersToHost)

logger = FormatAdapter(logging.getLogger(__name__))


class JavaCaller(object):
    """ Support class that holds all the stuff for running stuff in Java.
        This includes the work of preparing data for transmitting to Java and\
        back.

        This separates the choices of how to call the Java batch vs streaming,\
        jar locations, parameters, etc from the rest of the python code.
    """

    __slots__ = [
        "_chipxy_by_ethernet",
        # The folder holding sqlite databases etc.
        "_report_folder",
        # The call to get java to work. Including the path if required.
        "_java_call",
        # The local https://github.com/SpiNNakerManchester/JavaSpiNNaker
        "_java_spinnaker_path",
        # the folder to write the any json files into
        "_json_folder",
        # The machine
        "_machine",
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

    def __init__(self, json_folder, java_call, java_spinnaker_path=None,
                 java_properties=None):
        """ Creates a java caller and checks the user/config parameters.

        :param json_folder: The location where the machine JSON is written.
        :type json_folder: str
        :param java_call: Call to start java. Including the path if required.
        :type java_call: str
        :param java_spinnaker_path: the path where the java code can be found.
            This must point to a local copy of \
            https://github.com/SpiNNakerManchester/JavaSpiNNaker. \
            It must also have been built! \
            If None the assumption is that it is the same parent directory as \
            https://github.com/SpiNNakerManchester/SpiNNFrontEndCommon.
        :param java_properties:
            Optional properties that will be passed to Java.\
            Must start with ``-D``.
            For example ``-Dlogging.level=DEBUG``
        :type java_properties: str
        :raise ConfigurationException: if simple parameter checking fails.
        """
        self._recording = None
        self._report_folder = None
        self._json_folder = json_folder

        self._java_call = java_call
        result = subprocess.call([self._java_call, '-version'])
        if result != 0:
            raise ConfigurationException(
                " {} -version failed. "
                "Please set [Java] java_call to the absolute path "
                "to start java. (in config file)".format(self._java_call))

        if java_spinnaker_path is None:
            interface = os.path.dirname(os.path.realpath(__file__))
            spinn_front_end_common = os.path.dirname(interface)
            github_checkout_dir = os.path.dirname(spinn_front_end_common)
            parent = os.path.dirname(github_checkout_dir)
            self._java_spinnaker_path = os.path.join(
                parent, "JavaSpiNNaker")
        else:
            # As I don't know how to write pwd and /JavaSpiNNaker to one line
            indirect_path = os.path.join(
                java_spinnaker_path, "JavaSpiNNaker")
            if os.path.isdir(indirect_path):
                self._java_spinnaker_path = indirect_path
            else:
                self._java_spinnaker_path = java_spinnaker_path
        if not os.path.isdir(self._java_spinnaker_path):
            raise ConfigurationException(
                "No Java code found at {}".format(self._java_spinnaker_path))

        self._machine = None
        self._machine_json_path = None
        self._placement_json = None
        self._monitor_cores = None
        self._gatherer_iptags = None
        self._gatherer_cores = None
        self._java_properties = java_properties
        self._chipxy_by_ethernet = None
        if self._java_properties is not None:
            self._java_properties = self._java_properties.split()
            for _property in self._java_properties:
                if _property[:2] != "-D":
                    raise ConfigurationException(
                        "Java Properties must start with -D found at {}".
                        format(_property))

    def set_machine(self, machine):
        """ Passes the machine in leaving this class to decide pass it to Java.

        :param machine: A machine Object
        :type machine: ~spinn_machine.Machine
        """
        self._machine = machine

    def set_advanced_monitors(
            self, placements, tags, monitor_cores, packet_gathers):
        """
        :param placements: The placements of the vertices
        :type placements: ~pacman.model.placements.Placements
        :param tags: The tags assigned to the vertices
        :type tags: ~pacman.model.tags.Tags
        :param monitor_cores: Where the advanced monitor for each core is
        :type monitor_cores: dict(Vertex,Vertex)
        :param packet_gathers: Where the packet gatherers are
        :type packet_gathers: dict(Vertex,Vertex)
        :rtype: None
        """
        self._monitor_cores = dict()
        for core, monitor_core in monitor_cores.items():
            placement = placements.get_placement_of_vertex(monitor_core)
            self._monitor_cores[core] = placement.p

        self._gatherer_iptags = dict()
        self._gatherer_cores = dict()
        for core, packet_gather in packet_gathers.items():
            self._gatherer_iptags[core] = \
                tags.get_ip_tags_for_vertex(packet_gather)[0]
            placement = placements.get_placement_of_vertex(packet_gather)
            self._gatherer_cores[core] = placement.p

        self._chipxy_by_ethernet = defaultdict(list)
        for chip in self._machine.chips:
            if not chip.virtual:
                chip_xy = (chip.x, chip.y)
                ethernet = (chip.nearest_ethernet_x, chip.nearest_ethernet_y)
                self._chipxy_by_ethernet[ethernet].append(chip_xy)

    def _machine_json(self):
        """ Converts the machine in this class to JSON.

        :return: the name of the file containing the JSON
        """
        if self._machine_json_path is None:
            path = os.path.join(self._json_folder, "machine.json")
            self._machine_json_path = ConvertToJavaMachine.do_convert(
                self._machine, path)
        return self._machine_json_path

    def set_report_folder(self, report_folder):
        """ Passes the database file in.

        :param report_folder: Path to directory with SQLite databases\
            and into which java will write
        :type report_folder: str
        """
        self._report_folder = report_folder

    def set_placements(self, placements, transceiver):
        """ Passes in the placements leaving this class to decide pass it to\
            Java.

        This method may obtain extra information about he placements which is\
        why it also needs the transceiver.

        Currently the extra information extracted is recording region\
        base address but this could change if recording region saved in\
        the database.

        Currently this method uses JSON but that may well change to using the\
        database.

        :param placements: The Placements Object
        :type placements: ~pacman.model.placements.Placements
        :param transceiver: The Transceiver
        :type transceiver: ~spinnman.transceiver.Transceiver
        """
        path = os.path.join(self._json_folder, "java_placements.json")
        self._recording = False
        if self._gatherer_iptags is None:
            self._placement_json = self._write_placements(
                placements, transceiver, path)
        else:
            self._placement_json = self._write_gather(
                placements, transceiver, path)

    def _json_placement(self, placement, transceiver):

        vertex = placement.vertex
        json_placement = OrderedDict()
        json_placement["x"] = placement.x
        json_placement["y"] = placement.y
        json_placement["p"] = placement.p

        json_vertex = OrderedDict()
        json_vertex["label"] = vertex.label
        if isinstance(vertex, AbstractReceiveBuffersToHost) and \
                vertex.get_recorded_region_ids():
            self._recording = True
            json_vertex["recordedRegionIds"] = vertex.get_recorded_region_ids()
            json_vertex["recordingRegionBaseAddress"] = \
                vertex.get_recording_region_base_address(
                    transceiver, placement)
        else:
            json_vertex["recordedRegionIds"] = []
            json_vertex["recordingRegionBaseAddress"] = 0
        json_placement["vertex"] = json_vertex

        return json_placement

    def _json_iptag(self, iptag):
        json_tag = OrderedDict()
        json_tag["x"] = iptag.destination_x
        json_tag["y"] = iptag.destination_y
        json_tag["boardAddress"] = iptag.board_address
        json_tag["targetAddress"] = iptag.ip_address
        # Intentionally not including port!
        json_tag["stripSDP"] = iptag.strip_sdp
        json_tag["tagID"] = iptag.tag
        json_tag["trafficIdentifier"] = iptag.traffic_identifier

        return json_tag

    def _placements_grouped(self, placements):
        by_ethernet = defaultdict(lambda: defaultdict(list))
        for placement in placements:
            chip = self._machine.get_chip_at(placement.x, placement.y)
            chip_xy = (placement.x, placement.y)
            ethernet = (chip.nearest_ethernet_x, chip.nearest_ethernet_y)
            by_ethernet[ethernet][chip_xy].append(placement)
        return by_ethernet

    def _write_gather(self, placements, transceiver, path):

        placements_by_ethernet = self._placements_grouped(placements)
        json_obj = list()
        for ethernet in self._chipxy_by_ethernet:
            by_chip = placements_by_ethernet[ethernet]
            json_gather = OrderedDict()
            json_gather["x"] = ethernet[0]
            json_gather["y"] = ethernet[1]
            json_gather["p"] = self._gatherer_cores[ethernet]
            json_gather["iptag"] = self._json_iptag(
                self._gatherer_iptags[ethernet])
            json_chips = list()
            for chip_xy in self._chipxy_by_ethernet[ethernet]:
                json_chip = OrderedDict()
                json_chip["x"] = chip_xy[0]
                json_chip["y"] = chip_xy[1]
                json_chip["p"] = self._monitor_cores[chip_xy]
                if chip_xy in by_chip:
                    json_placements = list()
                    for placement in by_chip[chip_xy]:
                        json_p = self._json_placement(placement, transceiver)
                        if json_p:
                            json_placements.append(json_p)
                    if len(json_placements) > 0:
                        json_chip["placements"] = json_placements
                json_chips.append(json_chip)
            json_gather["monitors"] = json_chips
            json_obj.append(json_gather)

        # dump to json file
        with open(path, "w") as f:
            json.dump(json_obj, f)

        return path

    def _write_placements(self, placements, transceiver, path):
        # Read back the regions
        json_obj = list()
        for placement in placements:
            json_p = self._json_placement(placement, transceiver)
            if json_p:
                json_obj.append(json_p)

        # dump to json file
        with open(path, "w") as f:
            json.dump(json_obj, f)

        return path

    @property
    def _jar_file(self):
        f = os.path.join(
            self._java_spinnaker_path, "SpiNNaker-front-end",
            "target", "spinnaker-exe.jar")
        if not os.path.exists(f):
            logger.warning("no Java build in file {}; failure expected", f)
        return f

    def _run_java(self, *args):
        if self._java_properties is None:
            params = [self._java_call, '-jar', self._jar_file]
        else:
            params = [self._java_call] + self._java_properties \
                     + ['-jar', self._jar_file]
        params.extend(args)
        return subprocess.call(params)

    def get_all_data(self):
        """ Gets all the data from the previously set placements\
            and put these in the previously set database.
        """
        if not self._recording:
            return

        if self._gatherer_iptags is None:
            result = self._run_java(
                'download', self._placement_json, self._machine_json(),
                self._report_folder)
        else:
            result = self._run_java(
                'gather', self._placement_json, self._machine_json(),
                self._report_folder)
        if result != 0:
            log_file = os.path.join(self._report_folder, "jspin.log")
            raise PacmanExternalAlgorithmFailedToCompleteException(
                "Java call exited with value " + str(result) + " see "
                + str(log_file) + " for logged info")

    def execute_data_specification(self):
        """ Writes all the data specs, uploading the result to the machine.
        """
        result = self._run_java(
            'dse', self._machine_json(), self._report_folder)
        if result != 0:
            log_file = os.path.join(self._report_folder, "jspin.log")
            raise PacmanExternalAlgorithmFailedToCompleteException(
                "Java call exited with value " + str(result) + " see "
                + str(log_file) + " for logged info")

    def execute_system_data_specification(self):
        """ Writes all the data specs for system cores, \
            uploading the result to the machine.
        """
        result = self._run_java(
            'dse_sys', self._machine_json(), self._report_folder)
        if result != 0:
            log_file = os.path.join(self._report_folder, "jspin.log")
            raise PacmanExternalAlgorithmFailedToCompleteException(
                "Java call exited with value " + str(result) + " see "
                + str(log_file) + " for logged info")

    def execute_app_data_specification(self, use_monitors):
        """ Writes all the data specs for application cores, \
            uploading the result to the machine.

        .. note:
            May assume that system cores are already loaded and running.
        """
        if use_monitors:
            result = self._run_java(
                'dse_app_mon', self._placement_json, self._machine_json(),
                self._report_folder, self._report_folder)
        else:
            result = self._run_java(
                'dse_app', self._machine_json(), self._report_folder)
        if result != 0:
            log_file = os.path.join(self._report_folder, "jspin.log")
            raise PacmanExternalAlgorithmFailedToCompleteException(
                "Java call exited with value " + str(result) + " see "
                + str(log_file) + " for logged info")
