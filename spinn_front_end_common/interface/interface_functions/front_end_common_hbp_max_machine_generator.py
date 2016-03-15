import requests


class FrontEndCommonHBPMaxMachineGenerator(object):

    """ Generates the width and height of the maximum machine a given\
        HBP server can generate
    """

    def __call__(self, hbp_server_url, total_run_time):
        """

        :param hbp_server_url: The URL of the HBP server from which to get\
                    the machine
        :param total_run_time: The total run time to request
        :param partitioned_graph: The partitioned graph to allocate for
        """

        url = hbp_server_url
        if url.endswith("/"):
            url = url[:-1]

        max_machine_request = requests.get("{}/max".format(url))
        max_machine = max_machine_request.json()

        return {
            "max_width": max_machine["width"],
            "max_height": max_machine["height"]
        }
