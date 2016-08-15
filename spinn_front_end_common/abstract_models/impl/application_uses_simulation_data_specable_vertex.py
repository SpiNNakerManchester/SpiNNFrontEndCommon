from pacman.model.decorators.overrides import overrides
from pacman.executor.injection_decorator import requires_injection, inject, \
    supports_injection

from abc import abstractmethod

from spinn_front_end_common.abstract_models.impl.\
    uses_simulation_data_specable_vertex import \
    UsesSimulationDataSpecableVertex


@supports_injection
class ApplicationUsesSimulationDataSpecableVertex(
        UsesSimulationDataSpecableVertex):
    """

    """

    def __init__(self, machine_time_step, time_scale_factor):
        UsesSimulationDataSpecableVertex.__init__(
            self, machine_time_step, time_scale_factor)

        # data stores for basic generate dsg
        self._graph_mapper=None
        self._application_graph = None
        self._machine_graph = None
        self._routing_info = None
        self._placements = None
        self._iptags = None
        self._reverse_iptags = None

    @requires_injection(
        ["MemoryGraphMapper", "MemoryMachineGraph", "MemoryRoutingInfos",
         "MemoryApplicationGraph", "MemoryPlacements", "MemoryIpTags",
         "MemoryReverseIpTags"])
    @overrides(UsesSimulationDataSpecableVertex.generate_data_specification)
    def generate_data_specification(self, spec, placement):
        self.generate_application_data_specification(
            spec, placement, self._graph_mapper, self._application_graph,
            self._machine_graph, self._routing_info, self._iptags,
            self._reverse_iptags)

    @abstractmethod
    def generate_application_data_specification(
            self, spec, placement, graph_mapper, application_graph,
            machine_graph, routing_info, iptags, reverse_iptags):
        pass

    @inject("MemoryGraphMapper")
    def set_graph_mapper(self, graph_mapper):
        self._graph_mapper = graph_mapper

    @inject("MemoryMachineGraph")
    def set_machine_graph(self, machine_graph):
        self._machine_graph = machine_graph

    @inject("MemoryRoutingInfos")
    def set_routing_info(self, routing_info):
        self._routing_info = routing_info

    @inject("MemoryApplicationGraph")
    def set_application_graph(self, application_graph):
        self._application_graph = application_graph

    @inject("MemoryPlacements")
    def set_placements(self, placements):
        self._placements = placements

    @inject("MemoryIpTags")
    def set_iptags(self, iptags):
        self._iptags = iptags

    @inject("MemoryReverseIpTags")
    def set_reverse_iptags(self, reverse_iptags):
        self._reverse_iptags = reverse_iptags
