# Copyright (c) 2017-2022 The University of Manchester
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


class StreamingContextManager(object):
    """ The implementation of the context manager object for streaming \
        configuration control.
    """
    __slots__ = ["_gatherers"]

    def __init__(self, gatherers):
        """
        :param iterable(DataSpeedUpPacketGatherMachineVertex) gatherers:
        """
        self._gatherers = list(gatherers)

    def __enter__(self):
        for gatherer in self._gatherers:
            gatherer.load_system_routing_tables()
        for gatherer in self._gatherers:
            gatherer.set_cores_for_data_streaming()

    def __exit__(self, _type, _value, _tb):
        for gatherer in self._gatherers:
            gatherer.unset_cores_for_data_streaming()
        for gatherer in self._gatherers:
            gatherer.load_application_routing_tables()
        return False
