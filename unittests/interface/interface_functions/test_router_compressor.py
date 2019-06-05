import struct
import pytest

from spinn_machine.virtual_machine import virtual_machine
from spinnman.model.enums import CPUState
from spinnman.model import IOBuffer
from spinnman.utilities.appid_tracker import AppIdTracker
from pacman.model.routing_tables import (
    MulticastRoutingTables, MulticastRoutingTable)
from spinn_front_end_common.mapping_algorithms\
    .on_chip_router_table_compression.mundy_on_chip_router_compression import \
    MundyOnChipRouterCompression
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException


class MockTransceiverError(object):

    def __init__(self):
        self.app_id_tracker = AppIdTracker()

    def malloc_sdram(self, x, y, size, app_id, tag=None):
        # Always return 0 as doesn't matter here, because the write is also
        # mocked and does nothing
        return 0

    def write_memory(
            self, x, y, base_address, data, n_bytes=None, offset=0, cpu=0,
            is_filename=False):
        # Do nothing as it isn't really going to run
        pass

    def execute_application(self, executable_targets, app_id):
        # Do nothing as it isn't really going to run
        pass

    def wait_for_cores_to_be_in_state(
            self, all_core_subsets, app_id, cpu_states, timeout=None,
            time_between_polls=0.1,
            error_states=frozenset(
                {CPUState.RUN_TIME_EXCEPTION, CPUState.WATCHDOG}),
            counts_between_full_check=100):
        # Return immediately
        pass

    def get_user_0_register_address_from_core(self, p):
        # Just return 0 as the read is mocked too
        return 0

    def read_memory(self, x, y, base_address, length, cpu=0):
        # This will read the status, which will be 1 for "error"
        return struct.pack("<I", 1)

    def get_iobuf(self, core_subsets=None):
        # Yield a fake iobuf
        for core_subset in core_subsets:
            x = core_subset.x
            y = core_subset.y
            for p in core_subset.processor_ids:
                yield IOBuffer(x, y, p, "[ERROR] (Test): Compression Failed")

    def stop_application(self, app_id):
        # No need to stop nothing!
        pass


def test_router_compressor_on_error():
    compressor = MundyOnChipRouterCompression()
    routing_tables = MulticastRoutingTables(
        [MulticastRoutingTable(0, 0)])
    transceiver = MockTransceiverError()
    machine = virtual_machine(version=5)
    with pytest.raises(SpinnFrontEndException):
        compressor(
            routing_tables, transceiver, machine, app_id=17,
            provenance_file_path="")
