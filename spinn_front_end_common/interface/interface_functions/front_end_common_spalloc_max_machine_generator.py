from spalloc.protocol_client import ProtocolClient


class FrontEndCommonSpallocMaxMachineGenerator(object):
    """ Generates the width and height of the maximum machine a given\
        allocation server can generate
    """

    __slots__ = []

    def __call__(self, spalloc_server, spalloc_port=22244):

        client = ProtocolClient(spalloc_server, spalloc_port)
        client.connect()
        machines = client.list_machines()

        max_width = None
        max_height = None

        for machine in machines:
            if "default" in machine["tags"]:
                if ((max_width is None and max_height is None) or
                        ((machine["width"] * machine["height"]) >
                            (max_width * max_height))):
                    max_width = machine["width"]
                    max_height = machine["height"]

        return max_width * 12, max_height * 12
