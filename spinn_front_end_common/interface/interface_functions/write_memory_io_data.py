# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from spinn_utilities.progress_bar import ProgressBar
from pacman.model.graphs.application import ApplicationGraph
from spinnman.processes.fill_process import FillDataType
from spinnman.utilities.io import MemoryIO, FileIO
from spinnman.messages.spinnaker_boot import SystemVariableDefinition as SV
from spinn_front_end_common.abstract_models import AbstractUsesMemoryIO
from spinn_front_end_common.utilities.utility_objs import DataWritten
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGatherMachineVertex as
    Gatherer)


class _TranscieverDelegate(object):
    __slots__ = ["_txrx", "_writer"]

    def __init__(self, transceiver, write_memory_function):
        """
        :param ~.Transceiver transceiver:
        :param callable write_memory_function:
        """
        self._txrx = transceiver
        self._writer = write_memory_function

    def write_memory(self, x, y, base_address, data, n_bytes=None, offset=0,
                     cpu=0, is_filename=False):
        if self._writer is not None:
            self._writer(
                x, y, base_address, data, n_bytes, offset, cpu, is_filename)
        else:
            self._txrx.write_memory(
                x, y, base_address, data, n_bytes, offset, cpu, is_filename)

    def read_memory(self, x, y, base_address, length, cpu=0):
        return self._txrx.read_memory(x, y, base_address, length, cpu)

    def fill_memory(
            self, x, y, base_address, repeat_value, bytes_to_fill,
            data_type=FillDataType.WORD):
        self._txrx.fill_memory(
            x, y, base_address, repeat_value, bytes_to_fill, data_type)


class WriteMemoryIOData(object):
    """ An algorithm that handles objects implementing the interface\
        :py:class:`AbstractUsesMemoryIO`.
    """

    __slots__ = [
        # The next tag to use by chip
        "_next_tag",
        "_data_folder", "_machine", "_monitor_map", "_txrx", "_use_monitors",
        "_app_id", "_hostname", "_base_address_map", "_have_app_graph"
    ]

    _FILENAME_TEMPLATE = "{}_data_{}_{}_{}_{}.dat"

    def __init__(self):
        self._next_tag = dict()
        self._data_folder = None
        self._machine = None
        self._monitor_map = None
        self._txrx = None
        self._use_monitors = False
        self._app_id = 0
        self._hostname = ""
        self._base_address_map = None
        self._have_app_graph = False

    def __call__(
            self, placements, app_id, report_folder, hostname,
            app_graph=None, transceiver=None, uses_advanced_monitors=False,
            extra_monitor_cores_to_ethernet_connection_map=None,
            processor_to_app_data_base_address=None, machine=None):
        """
        :param ~pacman.model.placements Placements placements:
            The placements of vertices of the graph
        :param int app_id: The ID of the application
        :param str report_folder: The location of data files
        :param str hostname: The host name of the machine
        :param ~pacman.model.graphs.application.ApplicationGraph graph:
            The application graph that generated these vertices, if known.
            This algorithm only really cares whether it exists or not.
        :param ~spinnman.transceiver.Transceiver transceiver:
            The transceiver to write data using; if None only data files
            are written
        :param bool uses_advanced_monitors:
            Whether to use the Fast Data In protocol
        :param extra_monitor_cores_to_ethernet_connection_map:
            The mapping from chips to packet gatherer vertices.
            Only required when `uses_advanced_monitors = True`
        :type extra_monitor_cores_to_ethernet_connection_map:
            dict(tuple(int,int), DataSpeedUpPacketGatherMachineVertex)
        :param processor_to_app_data_base_address:
            Existing dictionary of processor to base address.
            Only required when `uses_advanced_monitors = True`
        :type processor_to_app_data_base_address:
            dict(tuple(int,int,int),DataWritten)
        :param ~spinn_machine.Machine machine:
        :return: The mapping between processor and addresses allocated
        :rtype: dict(tuple(int,int,int),DataWritten)
        """
        # pylint: disable=too-many-arguments
        if processor_to_app_data_base_address is None:
            self._base_address_map = dict()
        else:
            self._base_address_map = processor_to_app_data_base_address
        self._machine = machine
        self._txrx = transceiver
        self._use_monitors = uses_advanced_monitors
        self._monitor_map = extra_monitor_cores_to_ethernet_connection_map
        self._data_folder = report_folder
        self._hostname = hostname
        self._app_id = app_id
        self._have_app_graph = isinstance(app_graph, ApplicationGraph)

        progress = ProgressBar(
            sum(1 for _ in placements.placements), "Writing data")
        for placement in progress.over(placements.placements):
            vtx = self.__get_writer_vertex(placement.vertex)
            if vtx:
                # select the mode of writing and therefore buffer size
                write_memory_fun = self.__get_write_function(placement)
                self.__write_data_for_vertex(placement, vtx, write_memory_fun)

        return self._base_address_map

    def __get_writer_vertex(self, vertex):
        """ Get a vertex that can use the API to do the writing.

        Prefers the application vertex if one exists.

        :param ~.MachineVertex vertex:
        :rtype: AbstractUsesMemoryIO or None
        """
        if self._have_app_graph and isinstance(
                vertex.app_vertex, AbstractUsesMemoryIO):
            return vertex.app_vertex
        if isinstance(vertex, AbstractUsesMemoryIO):
            return vertex
        return None

    def __get_write_function(self, placement):
        """ Get how to write the vertex's data if writing for real.

        :param ~.Placement placement: The location (in a placement)
        :rtype: callable
        """
        # determine which function to use for writing memory
        return Gatherer.locate_correct_write_data_function_for_chip_location(
            machine=self._machine, x=placement.x, y=placement.y,
            transceiver=self._txrx, uses_advanced_monitors=self._use_monitors,
            extra_monitor_cores_to_ethernet_connection_map=self._monitor_map)

    def __get_used_tags(self, placement, heap_address):
        """ Get the tags that have already been used on the given chip

        :param ~.Placement placement:
            The x,y-coordinates of the chip, as a Placement
        :param int heap_address: The address of the heap to query for tags
        :return: The used tags
        :rtype: iterable(int)
        """
        for element in self._txrx.get_heap(
                placement.x, placement.y, heap=heap_address):
            if not element.is_free:
                yield element.tag

    def __remote_get_next_tag(self, placement):
        """ Get the next SDRAM tag to use for the Memory IO on a given chip

        :param ~.Placement placement:
            The x,y-coordinates of the chip, as a Placement
        :return: The next available tag
        """
        key = (placement.x, placement.y)
        if key not in self._next_tag:
            # Find the maximum tag already in use across the three areas
            max_tag = 0
            for area in (SV.sdram_heap_address, SV.system_ram_heap_address,
                         SV.system_sdram_heap_address):
                for tag in self.__get_used_tags(placement, area):
                    max_tag = max(max_tag, tag)
            self._next_tag[key] = max_tag + 1
        next_tag = self._next_tag[key]
        self._next_tag[key] = next_tag + 1
        return next_tag

    def __local_get_next_tag(self, placement):
        """ Get the next SDRAM tag to use for the File IO on a given chip

        :param ~.Placement placement:
            The x,y-coordinates of the chip, as a Placement
        :return: The next available tag
        :rtype: int
        """
        key = (placement.x, placement.y)  # could be other fields too
        next_tag = self._next_tag.get(key, 1)
        self._next_tag[key] = next_tag + 1
        return next_tag

    def __write_data_for_vertex(
            self, placement, writer_vertex, write_memory_function):
        """ Write the data for the given vertex, if it supports the interface

        :param ~.Placement placement:
            The placement of the machine vertex, i.e., where to write to.
        :param AbstractUsesMemoryIO writer_vertex:
            The vertex to write data for (might be an application vertex)
        :param callable write_memory_function:
            the function used to write data to spinnaker
        """
        size = writer_vertex.get_memory_io_data_size()
        if self._txrx is not None:
            tag = self.__remote_get_next_tag(placement)
            start_address = self._txrx.malloc_sdram(
                placement.x, placement.y, size, self._app_id, tag)
            delegate = _TranscieverDelegate(self._txrx, write_memory_function)
            with MemoryIO(delegate, placement.x, placement.y, start_address,
                          start_address + size) as io:
                writer_vertex.write_data_to_memory_io(io, tag)
        else:
            tag = self.__local_get_next_tag(placement)
            start_address = 0
            filename = os.path.join(
                self._data_folder, self._FILENAME_TEMPLATE.format(
                    self._hostname, placement.x, placement.y, placement.p,
                    tag))
            with FileIO(filename, 0, size) as io:
                writer_vertex.write_data_to_memory_io(io, tag)
        self._base_address_map[placement.location] = DataWritten(
            start_address, size, size)
