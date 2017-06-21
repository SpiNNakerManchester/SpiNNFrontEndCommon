from spalloc.protocol_client import ProtocolClient


class FrontEndCommonSpallocMaxMachineGenerator(object):
    """ Generates the width and height of the maximum machine a given\
        allocation server can generate
    """

    __slots__ = []

    def __call__(
            self, spalloc_server, spalloc_port=22244, spalloc_machine=None):

        client = ProtocolClient(spalloc_server, spalloc_port)
        client.connect()
        machines = client.list_machines()

        max_width = None
        max_height = None

        for machine in machines:
            if ((spalloc_machine is None and "default" in machine["tags"]) or
                    machine["name"] == spalloc_machine):

                # Get the width and height in chips
                width = machine["width"] * 12
                height = machine["height"] * 12

                # A specific exception is the 1-board machine, which is
                # represented as a 3 board machine with 2 dead boards.
                # In this case the width and height is 8
                if (machine["width"] == 1 and
                        machine["height"] == 1 and
                        len(machine["dead_boards"]) == 2):
                    width = 8
                    height = 8

                # The "biggest" board is the one with the most chips
                if ((max_width is None and max_height is None) or
                        ((width * height) > (max_width * max_height))):
                    max_width = width
                    max_height = height

        # Return the width and height, and make no assumption about
        # wrap arounds or version
        return max_width, max_height, None, None
