from pacman.model.graphs.application.application_graph import ApplicationGraph
from pacman.model.graphs.machine.machine_graph import MachineGraph

from spinn_front_end_common.abstract_models import AbstractUsesMemoryIO

from spinn_machine.utilities.progress_bar import ProgressBar

from spinnman.utilities.io import MemoryIO, FileIO
from spinnman.messages.spinnaker_boot.system_variable_boot_values \
    import SystemVariableDefinition

import os


class WriteMemoryIOData(object):

    __slots__ = [

        # The next tag to use by chip
        "_next_tag"
    ]

    def __init__(self):
        self._next_tag = dict()

    def __call__(
            self, graph, placements, app_id, app_data_runtime_folder, hostname,
            transceiver=None, graph_mapper=None):

        processor_to_app_data_base_address = dict()
        progress_bar = ProgressBar(
            len(list(placements.placements)), "Writing data")

        if isinstance(graph, ApplicationGraph):

            for placement in placements.placements:
                associated_vertex = graph_mapper.get_application_vertex(
                    placement.vertex)
                self._write_data_for_vertex(
                    transceiver, placement, associated_vertex, app_id,
                    app_data_runtime_folder, hostname,
                    processor_to_app_data_base_address)
                progress_bar.update()
        elif isinstance(graph, MachineGraph):
            for placement in placements.placements:
                self._write_data_for_vertex(
                    transceiver, placement, placement.vertex, app_id,
                    app_data_runtime_folder, hostname,
                    processor_to_app_data_base_address)
                progress_bar.update()
        progress_bar.end()

        return processor_to_app_data_base_address, True

    def _get_tags(self, heap):
        return [element.tag for element in heap if not element.is_free]

    def _get_next_tag(self, transceiver, x, y):
        if (x, y) not in self._next_tag:
            sdram_tags = self._get_tags(transceiver.get_heap(
                x, y, heap=SystemVariableDefinition.sdram_heap_address))
            sram_tags = self._get_tags(transceiver.get_heap(
                x, y, heap=SystemVariableDefinition.system_ram_heap_address))
            system_tags = self._get_tags(transceiver.get_heap(
                x, y, heap=SystemVariableDefinition.system_sdram_heap_address))

            max_tag = 0
            for tags in (sdram_tags, sram_tags, system_tags):
                if len(tags) > 0:
                    max_tag = max(max_tag, max(tags))
            self._next_tag[(x, y)] = max_tag + 1
        next_tag = self._next_tag[(x, y)]
        self._next_tag[(x, y)] = next_tag + 1
        return next_tag

    def _write_data_for_vertex(
            self, transceiver, placement, vertex, app_id,
            app_data_runtime_folder, hostname,
            processor_to_app_data_base_address):

        if isinstance(vertex, AbstractUsesMemoryIO):
            size = vertex.get_memory_io_data_size()
            if transceiver is not None:

                tag = self._get_next_tag(transceiver, placement.x, placement.y)
                start_address = transceiver.malloc_sdram(
                    placement.x, placement.y, size, app_id, tag)
                end_address = start_address + size
                memory_io = MemoryIO(
                    transceiver, placement.x, placement.y, start_address,
                    end_address)
                vertex.write_data_to_memory_io(memory_io, tag)
                memory_io.close()

                processor_to_app_data_base_address[
                    placement.x, placement.y, placement.p] = {
                        'start_address': start_address,
                        'memory_used': size,
                        'memory_written': size
                }
            else:
                tag = self._next_tag.get((placement.x, placement.y), 1)
                self._next_tag[placement.x, placement.y] = tag + 1
                application_data_file_name = \
                    app_data_runtime_folder + os.sep + \
                    "{}_data_{}_{}_{}_{}.dat".format(
                        hostname, placement.x, placement.y, placement.p, tag)
                file_io = FileIO(application_data_file_name, 0, size)
                vertex.write_data_to_memory_io(file_io, tag)
                file_io.close()
                processor_to_app_data_base_address[
                    placement.x, placement.y, placement.p] = {
                        'start_address': 0,
                        'memory_used': size,
                        'memory_written': size
                }
