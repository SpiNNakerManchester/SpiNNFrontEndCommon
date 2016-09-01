from pacman.model.decorators.overrides import overrides
from pacman.executor.injection_decorator import supports_injection
from pacman.executor.injection_decorator import inject_items

from spinn_front_end_common.abstract_models.\
    abstract_generates_data_specification import\
    AbstractGeneratesDataSpecification

from abc import abstractmethod


@supports_injection
class MachineDataSpecableVertex(AbstractGeneratesDataSpecification):

    @inject_items({
        "machine_graph": "MemoryMachineGraph",
        "routing_info": "MemoryRoutingInfos",
        "iptags": "MemoryIpTags",
        "reverse_iptags": "MemoryReverseIpTags",
        "machine_time_step": "MachineTimeStep",
        "time_scale_factor": "TimeScaleFactor"
    })
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "machine_graph", "routing_info", "iptags", "reverse_iptags",
            "machine_time_step", "time_scale_factor"
        })
    def generate_data_specification(
            self, spec, placement, machine_graph, routing_info, iptags,
            reverse_iptags, machine_time_step, time_scale_factor):
        self.generate_machine_data_specification(
            spec, placement, machine_graph, routing_info, iptags,
            reverse_iptags, machine_time_step, time_scale_factor)

    @abstractmethod
    def generate_machine_data_specification(
            self, spec, placement, machine_graph, routing_info, iptags,
            reverse_iptags, machine_time_step, time_scale_factor):
        pass
