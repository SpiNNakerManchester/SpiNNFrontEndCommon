# spinn_machine imports
from spinn_machine.virutal_machine import VirtualMachine


class FrontEndCommonVirtualMachineGenerator(object):
    """
    """

    def __call__(self, width, height, virtual_has_wrap_arounds,
                 version):
        """
        :param width: The width of the machine in chips
        :param height: The height of the machine in chips
        :param virtual_has_wrap_arounds: True if the machine is virtual and\
                should be created with wrap_arounds
        :return: None
        """

        machine = VirtualMachine(
            width=width, height=height,
            with_wrap_arounds=virtual_has_wrap_arounds,
            version=version)

        return {"machine": machine}
