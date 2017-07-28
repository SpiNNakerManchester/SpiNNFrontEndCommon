from spalloc import ProtocolClient


class SpallocMaxMachineGenerator(object):
    """ Generates the width and height of the maximum machine a given\
        allocation server can generate
    """

    __slots__ = []

    def __call__(
            self, spalloc_server, spalloc_port=22244, spalloc_machine=None):
        with ProtocolClient(spalloc_server, spalloc_port) as client:
            machines = client.list_machines()
            # Close the context immediately; don't want to keep this particular
            # connection around as there's not a great chance of this code
            # being rerun in this process any time soon.
        max_width = None
        max_height = None
        max_area = -1

        for machine in self._filter(machines, spalloc_machine):
            # Get the width and height in chips, and logical area in chips**2
            width, height, area = self._get_size(machine)

            # The "biggest" board is the one with the most chips
            if area > max_area:
                max_area = area
                max_width = width
                max_height = height

        # Return the width and height, and make no assumption about wrap-
        # arounds or version.
        return max_width, max_height, None, None

    @staticmethod
    def _filter(machines, filter):  # @ReservedAssignment
        if filter is None:
            return (m for m in machines if "default" in m["tags"])
        else:
            return (m for m in machines if m["name"] == filter)

    @staticmethod
    def _get_size(machine):
        # Get the width and height in chips
        width = machine["width"] * 12
        height = machine["height"] * 12

        # A specific exception is the 1-board machine, which is represented as
        # a 3 board machine with 2 dead boards. In this case the width and
        # height are 8.
        if (machine["width"] == 1 and
                machine["height"] == 1 and
                len(machine["dead_boards"]) == 2):
            width = 8
            height = 8

        return width, height, width * height
