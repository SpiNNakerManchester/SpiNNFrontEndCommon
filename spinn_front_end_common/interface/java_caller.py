import os
import subprocess

from spinn_front_end_common.utilities.exceptions import ConfigurationException


class JavaCaller(object):

    __slots__ = [
        "_java_call",
        "_javaspinnaker_path"
    ]

    def __init__(self, java_call, javaspinnaker_path=None):
        self._java_call = java_call
        if javaspinnaker_path:
            self._javaspinnaker_path = javaspinnaker_path
        else:
            interface = os.path.dirname(
                os.path.realpath(__file__))
            spinn_front_end_common = os.path.dirname(interface)
            SpiNNFrontEndCommon = os.path.dirname(spinn_front_end_common)
            parent = os.path.dirname(SpiNNFrontEndCommon)
            self._javaspinnaker_path = os.path.join(parent, "JavaSpiNNaker")
        if not os.path.isdir(self._javaspinnaker_path):
            raise ConfigurationException(
                "No Java code found at {}".format(self._javaspinnaker_path))
        result = subprocess.call([self._java_call, '-version'])
        if result != 0:
            raise ConfigurationException(
                " {} -version failed. "
                "Please set [Java] java_call to the absolute path "
                "to start java. (in config file)".format(self._java_call))
