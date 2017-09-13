import unittest
from testfixtures import LogCapture
import json
import logging
import httpretty
from spinn_front_end_common.interface.interface_functions.hbp_allocator \
    import _HBPJobController


class TestHBPAllocator(unittest.TestCase):

    @httpretty.activate
    def test_hbp_job_controller(self):

        logging.basicConfig(level=logging.INFO)
        httpretty.register_uri(
            httpretty.GET, "http://localhost/extendLease", body="")
        httpretty.register_uri(
            httpretty.GET, "http://localhost/checkLease",
            body=json.dumps({"allocated": True}))

        with LogCapture() as l:
            controller = _HBPJobController("http://localhost")
            controller.extend_allocation(1)
            result = controller._check_lease(0)
            assert result["allocated"] is True
            for record in l.records:
                if record.levelname == "INFO":
                    assert "Starting new HTTP connection" not in record.msg


if __name__ == "__main__":
    unittest.main()
