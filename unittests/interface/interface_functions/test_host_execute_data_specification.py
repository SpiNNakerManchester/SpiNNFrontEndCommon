import unittest
from tempfile import mktemp

from spinn_machine.virtual_machine import VirtualMachine

from spinn_storage_handlers.file_data_writer import FileDataWriter
from data_specification import constants

from spinn_front_end_common.interface.interface_functions \
    import HostExecuteDataSpecification

from data_specification.data_specification_generator \
    import DataSpecificationGenerator


class _MockCPUInfo(object):
    """ Pretend CPU Info object
    """

    def __init__(self, user_0):
        self._user_0 = user_0

    @property
    def user(self):
        return [self._user_0]


class _MockTransceiver(object):
    """ Pretend transceiver
    """

    def __init__(self, user_0_addresses):
        """

        :param user_0_addresses: dict of (x, y, p) to user_0_address
        """
        self._regions_written = list()
        self._user_0_addresses = user_0_addresses
        self._next_address = 0

    @property
    def regions_written(self):
        """ A list of tuples of (base_address, data) which has been written
        """
        return self._regions_written

    def malloc_sdram(self, x, y, size, app_id):
        address = self._next_address
        self._next_address += size
        return address

    def get_user_0_register_address_from_core(self, p):
        return self._user_0_addresses[p]

    def get_cpu_information_from_core(self, x, y, p):
        return _MockCPUInfo(self._user_0_addresses[(x, y, p)])

    def write_memory(
            self, x, y, base_address, data, n_bytes=None, offset=0,
            cpu=0, is_filename=False):
        self._regions_written.append((base_address, data))


class TestHostExecuteDataSpecification(unittest.TestCase):

    def test_call(self):
        executor = HostExecuteDataSpecification()
        transceiver = _MockTransceiver(user_0_addresses={0: 1000})
        machine = VirtualMachine(2, 2)

        # Write a data spec to execute
        temp_spec = mktemp()
        spec_writer = FileDataWriter(temp_spec)
        spec = DataSpecificationGenerator(spec_writer)
        spec.reserve_memory_region(0, 100)
        spec.reserve_memory_region(1, 100, empty=True)
        spec.reserve_memory_region(2, 100)
        spec.switch_write_focus(0)
        spec.write_value(0)
        spec.write_value(1)
        spec.write_value(2)
        spec.switch_write_focus(2)
        spec.write_value(3)
        spec.end_specification()

        # Execute the spec
        dsg_targets = {(0, 0, 0): temp_spec}
        executor.__call__(transceiver, machine, 30, dsg_targets)

        # Test regions - although 3 are created, only 2 should be uploaded
        # (0 and 2), and only the data written should be uploaded
        # The space between regions should be as allocated regardless of
        # how much data is written
        header_and_table_size = (constants.MAX_MEM_REGIONS + 2) * 4
        regions = transceiver.regions_written
        self.assertEqual(len(regions), 4)

        # Base address for header and table
        self.assertEqual(regions[0][0], 0)

        # Base address for region 0 (after header and table)
        self.assertEqual(regions[1][0], header_and_table_size)

        # Base address for region 2
        self.assertEqual(regions[2][0], header_and_table_size + 200)

        # User 0 write address
        self.assertEqual(regions[3][0], 1000)

        # Size of header and table
        self.assertEqual(len(regions[0][1]), header_and_table_size)

        # Size of region 0
        self.assertEqual(len(regions[1][1]), 12)

        # Size of region 2
        self.assertEqual(len(regions[2][1]), 4)

        # Size of user 0
        self.assertEqual(len(regions[3][1]), 4)


if __name__ == "__main__":
    unittest.main()
