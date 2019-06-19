import os
import logging
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.interface.profiling import AbstractHasProfileData
import numpy as np
from spinnak_ear.IHCAN_vertex import IHCANVertex
from spinnak_ear.OME_vertex import OMEVertex
from spinnak_ear.DRNL_vertex import DRNLVertex
from spinnak_ear.AN_group_vertex import ANGroupVertex


logger = logging.getLogger(__name__)


class ProfileDataGatherer(object):
    __slots__ = []

    def __call__(
            self, transceiver, placements, provenance_file_path,
            run_time_ms, machine_time_step):
        """
        :param transceiver: the SpiNNMan interface object
        :param placements: The placements of the vertices
        :param has_ran: token that states that the simulation has ran
        :param provenance_file_path: The location to store the profile data
        :param run_time_ms: runtime in ms
        :param machine_time_step: machine time step in ms
        """
        # pylint: disable=too-many-arguments
        machine_time_step_ms = float(machine_time_step) / 1000.0

        progress = ProgressBar(
            placements.n_placements, "Getting profile data")

        # retrieve provenance data from any cores that provide data
        for placement in progress.over(placements.placements):
            if isinstance(placement.vertex, AbstractHasProfileData) and not isinstance(placement.vertex,OMEVertex)\
                    and not isinstance(placement.vertex,DRNLVertex) and not isinstance(placement.vertex,IHCANVertex) \
                    and not isinstance(placement.vertex,ANGroupVertex):
                # get data
                profile_data = placement.vertex.get_profile_data(
                    transceiver, placement)
                if profile_data.tags:
                    self._write(placement, profile_data, run_time_ms,
                                machine_time_step_ms, provenance_file_path)
    def _write(self, p, profile_data, run_time_ms,
               machine_time_step_ms, directory):
        # pylint: disable=too-many-arguments
        max_tag_len = max([len(tag) for tag in profile_data.tags])

        spike_profile = profile_data.get_complete_profile('INCOMING_SPIKE')
        nonzero_rows_profile = profile_data.get_complete_profile('PROCESS_FIXED_SYNAPSES')
        timer_profile = profile_data.get_complete_profile('TIMER')
        spike_pro_overhead = np.asarray(
            [sum(spike_profile[start_index:nonzero_rows_profile[1][i] + 1]) for i, start_index in
             enumerate(nonzero_rows_profile[0])])

        timer_profile_minus_spike= np.subtract(timer_profile,spike_pro_overhead)
        np.savez_compressed(directory+'/{}_{}_{}_profile'.format(p.x, p.y, p.p),
                            spike_profile=spike_profile,timer_profile=timer_profile_minus_spike)

        # # write data
        # file_name = os.path.join(
        #     directory, "{}_{}_{}_profile.txt".format(p.x, p.y, p.p))
        #
        # # set mode of the file based off if the file already exists
        # mode = "w"
        # if os.path.exists(file_name):
        #     mode = "a"
        #
        # # write profile data to file
        # with open(file_name, mode) as f:
        #     f.write("{: <{}s} {: <7s} {: <14s} {: <14s} {: <14s}\n".format(
        #         "tag", max_tag_len, "n_calls", "mean_ms",
        #         "n_calls_per_ts", "mean_ms_per_ts"))
        #     f.write("{:-<{}s} {:-<7s} {:-<14s} {:-<14s} {:-<14s}\n".format(
        #         "", max_tag_len, "", "", "", ""))
        #     for tag in profile_data.tags:
        #         f.write("{: <{}s} {: >7d} {: >14.6f} {: >14.6f} {: >14.6f}\n"
        #                 .format(
        #                     tag, max_tag_len,
        #                     profile_data.get_n_calls(tag),
        #                     profile_data.get_mean_ms(tag),
        #                     profile_data.get_mean_n_calls_per_ts(
        #                         tag, run_time_ms, machine_time_step_ms),
        #                     profile_data.get_mean_ms_per_ts(
        #                         tag, run_time_ms, machine_time_step_ms)))
