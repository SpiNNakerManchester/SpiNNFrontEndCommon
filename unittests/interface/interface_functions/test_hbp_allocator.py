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

import unittest
import json
import logging
import time
import httpretty  # type: ignore[import]
from testfixtures import LogCapture  # type: ignore[import]
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.interface_functions.hbp_allocator \
    import (
        _HBPJobController)


class TestHBPAllocator(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    @httpretty.activate
    def test_hbp_job_controller(self):

        logging.basicConfig(level=logging.INFO)
        httpretty.register_uri(
            httpretty.GET, "http://localhost/extendLease", body="")
        httpretty.register_uri(
            httpretty.GET, "http://localhost/checkLease",
            body=json.dumps({"allocated": True}))
        httpretty.register_uri(
            httpretty.DELETE, "http://localhost/", body="")
        httpretty.register_uri(
            httpretty.PUT, "http://localhost/power", body="")
        httpretty.register_uri(
            httpretty.GET, "http://localhost/chipCoordinates",
            body=json.dumps([0, 1, 2]))

        with LogCapture() as lc:
            controller = _HBPJobController("http://localhost", "test_machine")
            try:
                controller.extend_allocation(1)
                result = controller._check_lease(0)
                assert result["allocated"] is True
                controller.set_power(False)
                assert not controller.power
                controller.set_power(True)
                assert controller.power
                (cabinet, frame, board) = controller.where_is_machine(0, 0)
                assert (cabinet, frame, board) == (0, 1, 2)
            finally:
                controller.close()
                time.sleep(2)
            for record in lc.records:
                if record.levelname == "INFO":
                    assert "Starting new HTTP connection" not in record.msg


if __name__ == "__main__":
    unittest.main()
