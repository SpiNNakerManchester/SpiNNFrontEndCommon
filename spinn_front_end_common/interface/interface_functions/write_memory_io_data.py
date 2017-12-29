from pacman.model.graphs.application import ApplicationGraph
from pacman.model.graphs.machine import MachineGraph

from spinn_front_end_common.abstract_models import AbstractUsesMemoryIO

from spinn_utilities.progress_bar import ProgressBar

from spinnman.utilities.io import MemoryIO, FileIO
from spinnman.messages.spinnaker_boot import SystemVariableDefinition as SV

import os


class WriteMemoryIOData(object):
    """ An algorithm that handles objects implementing the interface\
        AbstractUsesMemoryIO
    """

    __slots__ = [

        # The next tag to use by chip
        "_next_tag"
    ]

    def __init__(self):
        self._next_tag = dict()

    def __call__(
            self, graph, placements, app_id, app_data_runtime_folder, hostname,
            transceiver=None, graph_mapper=None,
            processor_to_app_data_base_address=None):
        """

        :param graph: The graph to process
        :param placements: The placements of vertices of the graph
        :param app_id: The id of the application
        :param app_data_runtime_folder: The location of data files
        :param hostname: The host name of the machine
        :param transceiver:\
            The transceiver to write data using; if None only data files\
            are written
        :param graph_mapper: The optional mapping between graphs
        :param processor_to_app_data_base_address:\
            Optional existing dictionary of processor to base address
        :return: The mapping between processor and addresses allocated
        """

        if processor_to_app_data_base_address is None:
            processor_to_app_data_base_address = dict()
        progress = ProgressBar(
            len(list(placements.placements)), "Writing data")

        if isinstance(graph, ApplicationGraph):
            for placement in progress.over(placements.placements):
                associated_vertex = graph_mapper.get_application_vertex(
                    placement.vertex)
                self._write_data_for_vertex(
                    transceiver, placement, associated_vertex, app_id,
                    app_data_runtime_folder, hostname,
                    processor_to_app_data_base_address)
        elif isinstance(graph, MachineGraph):
            for placement in progress.over(placements.placements):
                self._write_data_for_vertex(
                    transceiver, placement, placement.vertex, app_id,
                    app_data_runtime_folder, hostname,
                    processor_to_app_data_base_address)

        return processor_to_app_data_base_address

    def _get_used_tags(self, transceiver, x, y, heap_address):
        """ Get the tags that have already been used on the given chip

        :param transceiver: The transceiver to use to get the data
        :param x: The x-coordinate of the chip
        :param y: The y-coordinate of the chip
        :param heap_address: The address of the heap to query for tags
        :return: A tuple of used tags
        """
        heap = transceiver.get_heap(x, y, heap=heap_address)
        return (element.tag for element in heap if not element.is_free)

    def _get_next_tag(self, transceiver, x, y):
        """ Get the next SDRAM tag to use for the Memory IO on a given chip

        :param transceiver: The transceiver to use to query for used tags
        :param x: The x-coordinate of the chip
        :param y: The y-coordinate of the chip
        :return: The next available tag
        """
        xy = (x, y)
        if xy not in self._next_tag:
            # Find the maximum tag already in use across the three areas
            max_tag = 0
            for area in (SV.sdram_heap_address, SV.system_ram_heap_address,
                         SV.system_sdram_heap_address):
                for tag in self._get_used_tags(transceiver, x, y, area):
                    max_tag = max(max_tag, tag)
            self._next_tag[xy] = max_tag + 1
        next_tag = self._next_tag[xy]
        self._next_tag[xy] = next_tag + 1
        return next_tag

    def _write_data_for_vertex(
            self, transceiver, placement, vertex, app_id,
            app_data_runtime_folder, hostname, base_address_map):
        """ Write the data for the given vertex, if it supports the interface


        :param transceiver:\
            The transceiver to write data using; if None only data files\
            are written
        :param placement: The placement of the machine vertex
        :param vertex:\
            The vertex to write data for (might be an application vertex)
        :param app_id: The id of the application
        :param app_data_runtime_folder: The location of data files
        :param hostname: The host name of the machine
        :param base_address_map: Dictionary of processor to base address
        """
        if isinstance(vertex, AbstractUsesMemoryIO):
            size = vertex.get_memory_io_data_size()
            if transceiver is not None:
                tag = self._get_next_tag(transceiver, placement.x, placement.y)
                start_address = transceiver.malloc_sdram(
                    placement.x, placement.y, size, app_id, tag)
                end_address = start_address + size
                with MemoryIO(transceiver, placement.x, placement.y,
                              start_address, end_address) as io:
                    vertex.write_data_to_memory_io(io, tag)
            else:
                tag = self._next_tag.get((placement.x, placement.y), 1)
                self._next_tag[placement.x, placement.y] = tag + 1
                filename = os.path.join(
                    app_data_runtime_folder,
                    "{}_data_{}_{}_{}_{}.dat".format(
                        hostname, placement.x, placement.y, placement.p, tag))
                with FileIO(filename, 0, size) as io:
                    vertex.write_data_to_memory_io(io, tag)
                start_address = 0
            base_address_map[placement.x, placement.y, placement.p] = {
                'start_address': start_address,
                'memory_used': size,
                'memory_written': size}
