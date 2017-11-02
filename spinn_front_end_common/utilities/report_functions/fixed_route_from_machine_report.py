import os

from spinn_utilities.progress_bar import ProgressBar


class FixedRouteFromMachineReport(object):
    """ function for writing the fixed routes from the machine
    """

    def __call__(self, transceiver, machine, report_default_directory,
                 app_id, loaded_fixed_routes_on_machine_token):
        """ writing the fixed routes from the machine
        
        :param transceiver: spinnMan instance
        :param machine: SpiNNMachine instance
        :param report_default_directory: folder where reports reside
        :param loaded_fixed_routes_on_machine_token: token that states fixed \
        routes have been loaded
        :param app_id: the app id the fixed routes were loaded with
        :rtype: None 
        """

        if not loaded_fixed_routes_on_machine_token:
            raise loaded_fixed_routes_on_machine_token(
                "Needs to have loaded fixed route data for this to work.")

        file_name = os.path.join(
            report_default_directory, "fixed_route_routers")

        with open(file_name, "w") as output:
                self._write_fixed_routers(output, transceiver, machine, app_id)

    def _write_fixed_routers(self, output, transceiver, machine, app_id):
        """
        
        :param transceiver: 
        :param machine: 
        :return: 
        """
        progress = ProgressBar(machine.chips(), "Writing fixed route report")
        for chip in progress.over(machine.chips()):
            if not chip.virtual:
                fixed_route = \
                    transceiver.read_fixed_route(chip.x, chip.y, app_id)
                output.write(
                    "{: <3s}:{: <3s} contains route {: <10s} [Cores][Links]"
                    .format(
                        chip.x, chip.y, self._reduce_route_value(
                            fixed_route.processor_ids, fixed_route.link_ids),
                        self._expand_route_value(
                            fixed_route.processor_ids, fixed_route.link_ids)))

    @staticmethod
    def _reduce_route_value(processors_ids, link_ids):
        value = 0
        for link in link_ids:
            value += 1 << link
        for processor in processors_ids:
            value += 1 << (processor + 6)
        return value

    @staticmethod
    def _expand_route_value(processors_ids, link_ids):
        """ Convert a 32-bit route word into a string which lists the target cores\
            and links.
        """

        # Convert processor targets to readable values:
        route_string = "["
        separator = ""
        for processor in processors_ids:
            route_string += "{}{}".format(separator, processor)
            separator = ", "

        route_string += "] ["

        # Convert link targets to readable values:
        link_labels = {0: 'E', 1: 'NE', 2: 'N', 3: 'W', 4: 'SW', 5: 'S'}

        separator = ""
        for link in link_ids:
            route_string += "{}{}".format(separator, link_labels[link])
            separator = ", "
        route_string += "]"
        return route_string
