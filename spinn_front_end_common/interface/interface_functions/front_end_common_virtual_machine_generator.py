# spinn_machine imports
from spinn_machine.virtual_machine import VirtualMachine


class FrontEndCommonVirtualMachineGenerator(object):

    __slots__ = []

    def __call__(
            self, width=None, height=None, virtual_has_wrap_arounds=None,
            version=None, n_cpus_per_chip=18, with_monitors=True,
            down_chips=None, down_cores=None, down_links=None):
        """
        :param width: The width of the machine in chips
        :param height: The height of the machine in chips
        :param virtual_has_wrap_arounds: True if the machine\
                should be created with wrap_arounds
        :param version: The version of board to create
        :param n_cpus_per_chip: The number of cores to put on each chip
        :param with_monitors: If true, CPU 0 will be marked as a monitor
        """

        machine = VirtualMachine(
            width=width, height=height,
            with_wrap_arounds=virtual_has_wrap_arounds,
            version=version, n_cpus_per_chip=n_cpus_per_chip,
            with_monitors=with_monitors, down_chips=down_chips,
            down_cores=down_cores, down_links=down_links)

        # Work out and add the spinnaker links and FPGA links
        machine.add_spinnaker_links(version)
        machine.add_fpga_links(version)

        return machine
