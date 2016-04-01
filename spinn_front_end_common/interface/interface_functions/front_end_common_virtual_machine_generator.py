# spinn_machine imports
from spinn_machine.virtual_machine import VirtualMachine


class FrontEndCommonVirtualMachineGenerator(object):

    def __call__(
            self, width=None, height=None, virtual_has_wrap_arounds=False,
            version=None, n_cpus_per_chip=18, with_monitors=True):
        """
        :param width: The width of the machine in chips
        :param height: The height of the machine in chips
        :param virtual_has_wrap_arounds: True if the machine is virtual and\
                should be created with wrap_arounds
        :param version: The version of board to create
        :param n_cpus_per_chip: The number of cores to put on each chip
        :param with_monitors: If true, CPU 0 will be marked as a monitor
        :return: None
        """

        machine = VirtualMachine(
            width=width, height=height,
            with_wrap_arounds=virtual_has_wrap_arounds,
            version=version, n_cpus_per_chip=n_cpus_per_chip,
            with_monitors=with_monitors)

        return {"machine": machine}
