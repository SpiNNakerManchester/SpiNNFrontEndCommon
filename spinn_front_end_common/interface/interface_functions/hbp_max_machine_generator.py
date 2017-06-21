import requests


class FrontEndCommonHBPMaxMachineGenerator(object):

    """ Generates the width and height of the maximum machine a given\
        HBP server can generate
    """

    __slots__ = []

    def __call__(self, hbp_server_url, total_run_time):
        """

        :param hbp_server_url: The URL of the HBP server from which to get\
                    the machine
        :param total_run_time: The total run time to request
        """

        url = hbp_server_url
        if url.endswith("/"):
            url = url[:-1]

        max_machine_request = requests.get(
            "{}/max".format(url),
            params={'runTime': total_run_time})
        max_machine = max_machine_request.json()

        # Return the width and height and assume that it has wrap arounds
        return max_machine["width"], max_machine["height"], True
