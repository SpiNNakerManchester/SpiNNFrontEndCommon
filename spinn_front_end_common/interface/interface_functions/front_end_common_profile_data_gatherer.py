from spinn_utilities.progress_bar import ProgressBar

# front end common imports
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.interface.profiling.abstract_has_profile_data \
    import AbstractHasProfileData

import os


class FrontEndCommonProfileDataGatherer(object):
    __slots__ = []

    def __call__(
            self, transceiver, placements, has_ran, provenance_file_path,
            run_time_ms, machine_time_step):
        """
        :param transceiver: the SpiNNMan interface object
        :param placements: The placements of the vertices
        :param has_ran: token that states that the simulation has ran
        :param provenance_file_path: The location to store the profile data
        :param run_time_ms: runtime in ms
        :param machine_time_step: machine time step in ms
        """

        machine_time_step_ms = machine_time_step / 1000

        if not has_ran:
            raise exceptions.ConfigurationException(
                "This function has been called before the simulation has ran."
                " This is deemed an error, please rectify and try again")

        progress = ProgressBar(
            placements.n_placements, "Getting profile data")

        # retrieve provenance data from any cores that provide data
        for placement in progress.over(placements.placements):
            if isinstance(placement.vertex, AbstractHasProfileData):

                # get data
                profile_data = placement.vertex.get_profile_data(
                    transceiver, placement)

                if len(profile_data.tags) > 0:

                    # write data
                    file_name = os.path.join(
                        provenance_file_path, "{}_{}_{}_profile.txt".format(
                            placement.x, placement.y, placement.p))

                    # set mode of the file based off if the file already exists
                    mode = "w"
                    if os.path.exists(file_name):
                        mode = "a"

                    # write profile data to file
                    with open(file_name, mode) as writer:
                        writer.write(
                            "{: <10s} {: <7s} {: <7s} {: <14s} {: <14s}\n"
                            .format(
                                "tag", "n_calls", "mean_ms", "n_calls_per_ts",
                                "mean_ms_per_ts"))
                        writer.write(
                            "{:-<10s} {:-<7s} {:-<7s} {:-<14s} {:-<14s}\n"
                            .format(
                                "", "", "", "", ""))
                        for tag in profile_data.tags:
                            writer.write(
                                "{: <10s} {: >7d} {: >7.2f} {: >14.2f} "
                                "{: >14.2f}\n"
                                .format(
                                    tag, profile_data.get_n_calls(tag),
                                    profile_data.get_mean_ms(tag),
                                    profile_data.get_mean_n_calls_per_ts(
                                        tag, run_time_ms,
                                        machine_time_step_ms),
                                    profile_data.get_mean_ms_per_ts(
                                        tag, run_time_ms,
                                        machine_time_step_ms)))
