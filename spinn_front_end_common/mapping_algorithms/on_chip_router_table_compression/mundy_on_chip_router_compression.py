from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.interface.interface_functions.\
    front_end_common_load_executable_images import \
    FrontEndCommonLoadExecutableImages
from spinn_front_end_common.utilities.utility_objs.executable_targets import \
    ExecutableTargets
from spinn_machine.core_subsets import CoreSubsets
from spinn_storage_handlers.buffered_bytearray_data_storage import \
    BufferedBytearrayDataStorage

import os


class MundyOnChipRouterCompression(object):
    """
    Compressor that uses a on chip router compressor for speed optimisations.
    """

    SIZE_OF_A_SDRAM_ENTRY = 4 * 4
    SURPLUS_DATA_ENTRIES = 3 * 4

    def __call__(self, routing_tables, transceiver, compressor_app_id, machine,
                 app_app_id, store_on_sdram=False, sdram_tag=1):
        """

        :param routing_tables: the memory routing tables to be compressed
        :param app_id: the app-id used by the main application
        :param store_on_sdram: flag to say store it on sdram or in the
        routing table
        :param machine: the spinnaker machine representation
        :param transceiver: the spinnman interface
        :return: flag stating routing compression and loading hath been done
        """

        # figure size of sdram needed for each chip for storing the routing
        # table
        for routing_table in routing_tables:
            size_for_each_chip = \
                ((routing_table.number_of_entries *
                  self.SIZE_OF_A_SDRAM_ENTRY) + self.SURPLUS_DATA_ENTRIES)
            chip = machine.get_chip(routing_table.x, routing_table.y)
            if size_for_each_chip > chip.sdram:
                raise exceptions.ConfigurationException(
                    "There is not enough memory on the chip to write the "
                    "routing tables into.")

            # go to spinnman and ask for a memory region of that size per chip.
            base_address = transceiver.malloc_sdram(
                routing_table.x, routing_table.y, size_for_each_chip,
                compressor_app_id, sdram_tag)

            data = self._build_data(routing_table, app_app_id, store_on_sdram)

            # write sdram requirements per chip
            transceiver.write_memory(
                 routing_table.x, routing_table.y, base_address, data)

        # load the router compressor executable
        self._load_executables(
            routing_tables, compressor_app_id, transceiver, machine)

        # verify when the executable has finished
        self._poll_till_complete_or_error()

        # return loaded routing tables flag
        return True

    def _poll_till_complete_or_error(self):
        pass

    def _load_executables(
            self, routing_tables, compressor_app_id, transceiver, machine):
        """

        :param routing_tables:
        :param compressor_app_id:
        :return:
        """

        # build core subsets
        core_subsets = self._build_core_subsets(routing_tables, machine)

        # build binary path
        binary_path = os.path.join(self.__file__, "rt_minimise.aplx")

        # build executable targets

        executable_targets = ExecutableTargets()
        executable_targets.add_subsets(binary_path, core_subsets)

        executable_loader = FrontEndCommonLoadExecutableImages()
        success = executable_loader(
            executable_targets, compressor_app_id, transceiver, True)
        if not success:
            raise exceptions.ConfigurationException(
                "The app loader failed to load the executable for router "
                "compression.")


    def _build_data(self, routing_table, app_id, store_on_sdram):
        """

        :param routing_table:
        :param app_id:
        :param store_on_sdram:
        :return:
        """

        size_for_router_entries = \
            (routing_table.number_of_entries * self.SIZE_OF_A_SDRAM_ENTRY)
        data = bytearray()
        data.append(app_id)
        data.append(store_on_sdram)
        data.append(size_for_router_entries)

        for entry in routing_table.multicast_routing_entries:
            data.append(entry.routing_entry_key)
            data.append(entry.mask)
            data.append(self._make_route(entry))
            data.append(self._make_source_hack(entry))

        writer = BufferedBytearrayDataStorage()
        writer.write(data)
        return writer

    @staticmethod
    def _make_route(entry):


    @staticmethod
    def _make_source_hack(entry):


    def _build_core_subsets(self, routing_tables, machine):
        """

        :param routing_tables: the routing tables to be loaded for compression
        :return: a core subsets representing all the routing tables
        """
        core_sets = CoreSubsets()
        for routing_table in routing_tables:
            # get the first none monitor core
            chip = machine.get_chip(routing_table.x, routing_table.y)
            processor = chip.get_first_none_monitor_processor()

            # add to the core subsets
            core_sets.add_processor(routing_table.x, routing_table.y,
                                    processor.processor_id)
        return core_sets



