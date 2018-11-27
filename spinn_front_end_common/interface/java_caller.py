from collections import defaultdict, OrderedDict
import json
import os
import subprocess

from pacman.exceptions import PacmanExternalAlgorithmFailedToCompleteException
from pacman.utilities.file_format_converters.convert_to_java_machine import \
    ConvertToJavaMachine
from spinn_front_end_common.utilities.exceptions import ConfigurationException


class JavaCaller(object):
    """ Support class that holds all the stuff for running stuff in Java.

        This includes the work of preparing data for transmitting to Java and
        back.

        This seperates the choices of how to call the Java batch vs streaming,
            jar locations, paramters ect from the rest of the python code.
    """

    __slots__ = [
        # The sqllite databse
        "_database_file",
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
        # Dict of chip (x, y) to the p of the montitor vertex
        "_monitor_cores",
        # Dict of ethernet (x, y) and tha packetGather IPtago
        "_gatherer_iptags",
        # Dict of ethernet (x, y) to the p of the packetGather vertex
        "_gatherer_cores",
        # The location where the latest placement json is written
        "_placement_json"
    ]

    def __init__(self, json_folder, java_call, java_spinnaker_path=None):
        """
        Creates a Jason caller and checks the user/ config parameters

        :param json_folder: The location where the machine json is written.
        :type json_folder: str
        :param java_call: Call to start java. Including the path if required.
        :type java_call: str
        :param java_spinnaker_path: the path where the java code can be found.
            This must point to a local copy of \
            https://github.com/SpiNNakerManchester/JavaSpiNNaker. \
            It must also have been built! \
            If None the assumption is that it is the same parent directory as \
            https://github.com/SpiNNakerManchester/SpiNNFrontEndCommon.
        :raise ConfigurationException if simple parameter checking fails.
        """
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
            self._java_spinnaker_path = os.path.join(parent, "JavaSpiNNaker")
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

    def set_machine(self, machine):
        """
        Passes the machine in leaving this class to decide pass it to Java.

        :param machine: A machine Object
        """
        self._machine = machine

    def set_advanced_monitors(
            self, placements, tags, monitor_cores, packet_gathers):
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

    def _machine_json(self):
        """
        Passes the machine in leaving this class to decide pass it to Java.

        :param machine: A machine Object
        """
        if self._machine_json_path is None:
            algo = ConvertToJavaMachine()
            path = os.path.join(self._json_folder, "machine.json")
            self._machine_json_path = algo(self._machine, path)
        return self._machine_json_path

    def set_database(self, database_file):
        """
        Passes the database file in.

        :param database_file: Path to the sql lite databse
        :type database_file: str
        """
        self._database_file = database_file

    def set_placements(self, placements, transceiver, monitor_cores=None,
                       packet_gathers=None):
        """
        Passes in the placements leaving this class to decide pass it to Java.

        This method may obtain extra information about he placements which is \
            why it also needs the transceiver.

        Currently the extra information extracted is recording region
            base address but this could change if recording region saved in
            the database.

        Currently this method uses json but that may well change to using the
            database.

        :param placements: The Placements Object
        :param transceiver: The Transceiver
        """

        path = os.path.join(self._json_folder, "java_placements.json")
        if self._gatherer_iptags is None:
            self._placement_json = self._write_placements(
                placements, transceiver, path)
        else:
            self._placement_json = self._write_gather(
                placements, transceiver, path)

    @staticmethod
    def _json_placement(placement, transceiver):

        json_placement = OrderedDict()
        json_placement["x"] = placement.x
        json_placement["y"] = placement.x
        json_placement["p"] = placement.p

        vertex = placement.vertex
        json_vertex = OrderedDict()
        json_vertex["label"] = vertex.label
        json_vertex["recordedRegionIds"] = vertex.get_recorded_region_ids()
        json_vertex["recordingRegionBaseAddress"] = \
            vertex.get_recording_region_base_address(
                transceiver, placement)
        json_placement["vertex"] = json_vertex

        return json_placement

    @staticmethod
    def _json_iptag(iptag):
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

        by_ethernet = self._placements_grouped(placements)
        json_obj = list()
        for ethernet, by_chip in by_ethernet.items():
            json_gather = OrderedDict()
            json_gather["x"] = ethernet[0]
            json_gather["y"] = ethernet[1]
            json_gather["p"] = self._gatherer_cores[ethernet]
            json_gather["iptag"] = self._json_iptag(
                self._gatherer_iptags[ethernet])
            json_chips = list()
            for chip_xy, placements in by_chip.items():
                json_chip = OrderedDict()
                json_chip["x"] = chip_xy[0]
                json_chip["y"] = chip_xy[1]
                json_chip["p"] = self._monitor_cores[chip_xy]
                json_placements = list()
                for placement in placements:
                    json_placements.append(
                        self._json_placement(placement, transceiver))
                json_chip["placements"] = json_placements
                json_chips.append(json_chip)
            json_gather["monitors"] = json_chips
        json_obj.append(json_gather)

        # dump to json file
        with open(path, "w") as f:
            json.dump(json_obj, f)

        return path

    @staticmethod
    def _write_placements(placements, transceiver, path):

        # Read back the regions
        json_obj = list()
        for placement in placements:
            json_obj.append(JavaCaller._json_placement(placement, transceiver))

        # dump to json file
        with open(path, "w") as f:
            json.dump(json_obj, f)

        return path

    def get_all_data(self):
        """
        Gets all the data from the previously set placements
        and put these in the previously set database.

        """
        jar_file = os.path.join(
            self._java_spinnaker_path, "SpiNNaker-front-end",
            "target", "spinnaker-exe.jar")
        if self._gatherer_iptags is None:
            result = subprocess.call(
                [self._java_call, '-jar', jar_file, 'upload',
                 self._placement_json, self._machine_json(),
                 self._database_file])
        else:
            result = subprocess.call(
                [self._java_call, '-jar', jar_file, 'gather',
                 self._placement_json, self._machine_json(),
                 self._database_file])
        if result != 0:
            raise PacmanExternalAlgorithmFailedToCompleteException(
                "Java call exited with value " + str(result))
