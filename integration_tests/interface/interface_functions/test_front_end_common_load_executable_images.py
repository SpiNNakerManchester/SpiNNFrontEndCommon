from spinn_front_end_common.interface.interface_functions\
    .front_end_common_load_executable_images \
    import FrontEndCommonLoadExecutableImages
from spinnman.transceiver import Transceiver
from spinnman.model.executable_targets import ExecutableTargets
from collections import defaultdict
import unittest


class _MockTransceiver(Transceiver):

    def __init__(self, test_case):
        self._test_case = test_case
        self._n_cores_in_app = defaultdict(lambda: 0)
        self._executable_on_core = dict()

    def execute_flood(
            self, core_subsets, executable, app_id, n_bytes=None, wait=False,
            is_filename=False):
        for core_subset in core_subsets.core_subsets:
            x = core_subset.x
            y = core_subset.y
            for p in core_subset.processor_ids:
                self._test_case.assertNotIn(
                    (x, y, p), self._executable_on_core)
                self._executable_on_core[x, y, p] = executable
        self._n_cores_in_app[app_id] += len(core_subsets)

    def get_core_state_count(self, app_id, state):
        return self._n_cores_in_app[app_id]

    def send_signal(self, app_id, signal):
        pass


class TestFrontEndCommonLoadExecutableImages(unittest.TestCase):

    def test_front_end_common_load_executable_images(self):
        transceiver = _MockTransceiver(self)
        loader = FrontEndCommonLoadExecutableImages()
        targets = ExecutableTargets()
        targets.add_processor("test.aplx", 0, 0, 0)
        targets.add_processor("test.aplx", 0, 0, 1)
        targets.add_processor("test.aplx", 0, 0, 2)
        targets.add_processor("test2.aplx", 0, 1, 0)
        targets.add_processor("test2.aplx", 0, 1, 1)
        targets.add_processor("test2.aplx", 0, 1, 2)
        loader.__call__(targets, 30, transceiver, True)


if __name__ == "__main__":
    unittest.main()
