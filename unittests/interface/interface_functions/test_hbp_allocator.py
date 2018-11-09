import unittest
import json
import logging
import time
import httpretty
from testfixtures import LogCapture
from spinn_front_end_common.interface.interface_functions.hbp_allocator \
    import (
        _HBPJobController)


class TestHBPAllocator(unittest.TestCase):

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
