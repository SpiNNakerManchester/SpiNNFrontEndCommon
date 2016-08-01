from pacman.model.decorators.overrides import overrides
from pacman.executor.injection_decorator import requires_injection, inject, \
    supports_injection

from spinn_front_end_common.abstract_models.impl.data_specable_vertex import \
    DataSpecableVertex

from abc import abstractmethod


@supports_injection
class MachineDataSpecableVertex(DataSpecableVertex):

    def __init__(self):
        DataSpecableVertex.__init__(self)

        # data stores for basic generate dsg
        self._machine_graph = None
        self._routing_info = None
        self._placements = None
        self._iptags = None
        self._reverse_iptags = None

    @requires_injection(
        ["MemoryMachineGraph", "MemoryRoutingInfos", "MemoryPlacements",
         "MemoryIpTags", "MemoryReverseIpTags"])
    @overrides(DataSpecableVertex.generate_data_specification)
    def generate_data_specification(self, spec, placement):
        self.generate_machine_data_specification(
            spec, placement, self._machine_graph, self._routing_info,
            self._iptags, self._reverse_iptags)

    @abstractmethod
    def generate_machine_data_specification(
            self, spec, placement, machine_graph, routing_info, iptags,
            reverse_iptags):
        pass

    @inject("MemoryMachineGraph")
    def set_machine_graph(self, machine_graph):
        self._machine_graph = machine_graph

    @inject("MemoryRoutingInfos")
    def set_routing_info(self, routing_info):
        self._routing_info = routing_info

    @inject("MemoryPlacements")
    def set_placements(self, placements):
        self._placements = placements

    @inject("MemoryIpTags")
    def set_iptags(self, iptags):
        self._iptags = iptags

    @inject("MemoryReverseIpTags")
    def set_reverse_iptags(self, reverse_iptags):
        self._reverse_iptags = reverse_iptags
