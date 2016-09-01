from pacman.model.decorators.overrides import overrides
from pacman.executor.injection_decorator import inject_items
from pacman.executor.injection_decorator import supports_injection

from spinn_front_end_common.abstract_models.\
    abstract_generates_data_specification import\
    AbstractGeneratesDataSpecification

from abc import abstractmethod


@supports_injection
class ApplicationDataSpecableVertex(AbstractGeneratesDataSpecification):

    @inject_items({
        "graph_mapper": "MemoryGraphMapper",
        "machine_graph": "MemoryMachineGraph",
        "routing_info": "MemoryRoutingInfos",
        "application_graph": "MemoryApplicationGraph",
        "tags": "MemoryTags",
        "machine_time_step": "MachineTimeStep",
        "time_scale_factor": "TimeScaleFactor"
    })
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "graph_mapper", "application_graph", "machine_graph",
            "routing_info", "tags", "machine_time_step",
            "time_scale_factor"
        })
    def generate_data_specification(
            self, spec, placement, graph_mapper, application_graph,
            machine_graph, routing_info, tags,
            machine_time_step, time_scale_factor):
        iptags = tags.get_ip_tags_for_vertex(placement.vertex)
        reverse_iptags = tags.get_reverse_ip_tags_for_vertex(placement.vertex)
        self.generate_application_data_specification(
            spec, placement, graph_mapper, application_graph, machine_graph,
            routing_info, iptags, reverse_iptags, machine_time_step,
            time_scale_factor)

    @abstractmethod
    def generate_application_data_specification(
            self, spec, placement, graph_mapper, application_graph,
            machine_graph, routing_info, iptags, reverse_iptags,
            machine_time_step, time_scale_factor):
        pass
