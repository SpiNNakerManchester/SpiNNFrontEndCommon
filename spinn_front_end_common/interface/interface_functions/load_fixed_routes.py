from spinn_utilities.progress_bar import ProgressBar


class LoadFixedRoutes(object):
    """ Load a set of fixed routes onto a SpiNNaker machine.
    """

    def __call__(self, fixed_routes, transceiver, app_id):

        progress_bar = ProgressBar(
            total_number_of_things_to_do=len(fixed_routes),
            string_describing_what_being_progressed="loading fixed routes")

        for chip_x, chip_y in progress_bar.over(fixed_routes.keys()):
            transceiver.load_fixed_route(
                chip_x, chip_y, fixed_routes[(chip_x, chip_y)], app_id)
