import unittest

import ConfigParser

from spinn_front_end_common.interface.abstract_spinnaker_base \
    import AbstractSpinnakerBase
from spinn_front_end_common.utilities.utility_objs.executable_finder \
    import ExecutableFinder
from spinn_front_end_common.utilities import globals_variables
from spinn_front_end_common.utilities.failed_state import FailedState


class Close_Once(object):

    __slots__ = ("closed")

    def __init__(self):
        self.closed = False

    def close(self):
        if self.closed:
            raise Exception("Close called twice")
        else:
            self.closed = True


class TestSpinnakerMainInterface(unittest.TestCase):

    def setUp(self):
        globals_variables.set_failed_state(FailedState())

    def default_config(self):
        config = ConfigParser.RawConfigParser()
        config.add_section("Mapping")
        config.set("Mapping", "extra_xmls_paths", value="")
        config.add_section("Machine")
        config.set("Machine", "appID", value="1")
        config.set("Machine", "virtual_board", value="False")
        config.add_section("Reports")
        config.set("Reports", "reportsEnabled", value="False")
        config.set("Reports", "defaultReportFilePath", value="DEFAULT")
        config.set("Reports", "max_reports_kept", value="1")
        config.set("Reports", "max_application_binaries_kept", value="1")
        config.set("Reports", "defaultApplicationDataFilePath",
                   value="DEFAULT")
        config.set("Reports", "writeAlgorithmTimings", value="False")
        config.set("Reports", "display_algorithm_timings", value="False")
        config.set("Reports", "provenance_format", value="xml")
        config.add_section("SpecExecution")
        config.set("SpecExecution", "specExecOnHost", value="True")

        return config

    def test_min_init(self):
        AbstractSpinnakerBase(
            self.default_config(), ExecutableFinder())

    def test_stop_init(self):
        interface = AbstractSpinnakerBase(
            self.default_config(), ExecutableFinder())
        mock_contoller = Close_Once()
        interface._machine_allocation_controller = mock_contoller
        self.assertFalse(mock_contoller.closed)
        interface.stop(turn_off_machine=False, clear_routing_tables=False,
                       clear_tags=False)
        self.assertTrue(mock_contoller.closed)
        interface.stop(turn_off_machine=False, clear_routing_tables=False,
                       clear_tags=False)

    def test_temp_defaultApplicationDataFilePath(self):
        config = self.default_config()
        config.set("Reports", "defaultApplicationDataFilePath", value="TEMP")
        AbstractSpinnakerBase(
            config, ExecutableFinder())


if __name__ == "__main__":
    unittest.main()
