from collections import OrderedDict
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
        "_javaspinnaker_path",
        # the folder to write the any json files into
        "_json_folder",
        # The location where the machine json is written
        "_machine_json",
        # The location where the latest placement json is written
        "_placement_json"
    ]

    def __init__(self, json_folder, java_call, javaspinnaker_path=None):
        """
        Creates a Jason caller and checks the user/ config parameters

        :param json_folder: The location where the machine json is written.
        :type json_folder: str
        :param java_call: Call to start java. Including the path if required.
        :type java_call: str
        :param javaspinnaker_path: the path where the java code can be found.
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

        if javaspinnaker_path is None:
            interface = os.path.dirname(os.path.realpath(__file__))
            spinn_front_end_common = os.path.dirname(interface)
            spinnfrontendcommon = os.path.dirname(spinn_front_end_common)
            parent = os.path.dirname(spinnfrontendcommon)
            self._javaspinnaker_path = os.path.join(parent, "JavaSpiNNaker")
        else:
            self._javaspinnaker_path = javaspinnaker_path
        if not os.path.isdir(self._javaspinnaker_path):
            raise ConfigurationException(
                "No Java code found at {}".format(self._javaspinnaker_path))

        self._machine_json = None
        self._placement_json = None

    def set_machine(self, machine):
        """
        Passes the machine in leaving this class to decide pass it to Java.

        :param machine: A machine Object
        """

        algo = ConvertToJavaMachine()
        path = os.path.join(self._json_folder, "machine.json")
        self._machine_json = algo(machine, path)

    def set_database(self, database_file):
        """
        Passes the database file in.

        :param database_file: Path to the sql lite databse
        :type database_file: str
        """
        self._database_file = database_file

    def set_placements(self, placements, transceiver):
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
        self._placement_json = self._write_placements(
            placements, transceiver, path)

    def _write_placements(self, placements, transceiver, path):

        # Read back the regions
        json_obj = list()
        for placement in placements:
            json_placement = OrderedDict()
            json_placement["x"] = placement.x
            json_placement["y"] = placement.y
            json_placement["p"] = placement.p
            vertex = placement.vertex
            json_vertex = OrderedDict()
            json_vertex["label"] = vertex.label
            json_vertex["recordedRegionIds"] = vertex.get_recorded_region_ids()
            json_vertex["recordingRegionBaseAddress"] = \
                vertex.get_recording_region_base_address(
                    transceiver, placement)
            json_placement["vertex"] = json_vertex
            json_obj.append(json_placement)

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
            self._javaspinnaker_path, "SpiNNaker-front-end",
            "target", "spinnaker-exe.jar")
        result = subprocess.call(
            [self._java_call, '-jar', jar_file, 'upload',
             self._placement_json, self._machine_json, self._database_file])
        if result != 0:
            raise PacmanExternalAlgorithmFailedToCompleteException(
                "Java call exited with value " + str(result))
