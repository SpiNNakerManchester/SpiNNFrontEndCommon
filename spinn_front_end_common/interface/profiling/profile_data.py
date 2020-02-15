# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import numpy
import math
import scipy.stats
from spinn_utilities.log import FormatAdapter

logger = FormatAdapter(logging.getLogger(__name__))

# Define profiler time scale in ms
_MS_SCALE = (1.0 / 200000.0)

# Define the positions in tags
_START_TIME = 0
_DURATION = 1


class ProfileData(object):
    """ A container for profile data
    """
    # pylint: disable=assignment-from-no-return

    START_TIME = _START_TIME
    DURATION = _DURATION

    __slots__ = (
        # A dictionary of tag label to numpy array of start times and durations
        "_tags",

        # A list of tag labels indexed by the tag ID
        "_tag_labels",

        # The maximum time recorded
        "_max_time"
    )

    def __init__(self, tag_labels):
        """
        :param tag_labels: A list of labels indexed by tag ID
        :type tag_labels: list(str)
        """
        self._tag_labels = tag_labels
        self._tags = dict()
        self._max_time = None

    def add_data(self, data):
        """ Add profiling data read from the profile section

        :param data: Data read from the profile section on the machine
        :type data: bytearray
        """
        samples = numpy.asarray(data, dtype="uint8").view(dtype="<u4")

        # Slice data to separate times, tags and flags
        sample_times = samples[::2]
        sample_tags_and_flags = samples[1::2]

        # Further split the tags and flags word into separate arrays of tags
        # and flags
        sample_tags = numpy.bitwise_and(sample_tags_and_flags, 0x7FFFFFFF)
        sample_flags = numpy.right_shift(sample_tags_and_flags, 31)

        # Find indices of samples relating to entries and exits
        sample_entry_indices = numpy.where(sample_flags == 1)
        sample_exit_indices = numpy.where(sample_flags == 0)

        # Convert count-down times to count up times from 1st sample
        sample_times_ms = numpy.multiply(
            numpy.subtract(sample_times[0], sample_times),
            _MS_SCALE, dtype=numpy.float)

        # Slice tags and times into entry and exits
        entry_tags = sample_tags[sample_entry_indices]
        entry_times_ms = sample_times_ms[sample_entry_indices]
        exit_tags = sample_tags[sample_exit_indices]
        exit_times_ms = sample_times_ms[sample_exit_indices]

        # Loop through unique tags
        for tag in numpy.unique(sample_tags):
            self._add_tag_data(
                entry_tags, entry_times_ms, exit_tags, exit_times_ms, tag)

    def _add_tag_data(
            self, entry_tags, entry_times, exit_tags, exit_times, tag):
        # pylint: disable=too-many-arguments
        tag_label = self._tag_labels.get(tag, None)
        if tag_label is None:
            logger.warning("Unknown tag {} in profile data", tag)
            tag_label = "UNKNOWN"

        # Get indices where these tags occur
        tag_entry_indices = numpy.where(entry_tags == tag)
        tag_exit_indices = numpy.where(exit_tags == tag)

        # Use these to get subset for this tag
        tag_entry_times = entry_times[tag_entry_indices]
        tag_exit_times = exit_times[tag_exit_indices]

        # If the first exit is before the first
        # Entry, add a dummy entry at beginning
        if tag_exit_times[0] < tag_entry_times[0]:
            logger.warning("Profile starts mid-tag")
            tag_entry_times = numpy.append(0.0, tag_entry_times)

        if len(tag_entry_times) > len(tag_exit_times):
            logger.warning("profile finishes mid-tag")
            tag_entry_times = tag_entry_times[
                :len(tag_exit_times) - len(tag_entry_times)]

        # Subtract entry times from exit times to get durations of each
        # call in ms
        tag_durations = numpy.subtract(tag_exit_times, tag_entry_times)

        # Add entry times and durations to dictionary
        self._tags[tag_label] = (tag_entry_times, tag_durations)

        # Keep track of the maximum time
        self._max_time = numpy.max(tag_entry_times + tag_durations)

    @property
    def tags(self):
        """ The tags recorded as labels

        :rtype: list(str)
        """
        return self._tags.keys()

    def get_mean_ms(self, tag):
        """ Get the mean time in milliseconds spent on operations with the\
            given tag

        :param tag: The tag to get the mean time for
        :type tag: str
        :rtype: float
        """
        return numpy.average(self._tags[tag][_DURATION])

    def get_n_calls(self, tag):
        """ Get the number of times the given tag was recorded

        :param tag: The tag to get the number of calls of
        :type tag: str
        :rtype: int
        """
        return self._tags[tag][_DURATION].size

    def get_mean_n_calls_per_ts(self, tag, machine_time_step_ms):
        """ Get the mean number of times the given tag was recorded per\
            timestep

        :param tag: The tag to get the data for
        :type tag: str
        :param machine_time_step_ms:\
            The time step of the simulation in microseconds
        :type machine_time_step_ms: int
        :rtype: float
        """
        n_points = math.ceil(
            self._max_time / machine_time_step_ms)
        endpoint = n_points * machine_time_step_ms
        bins = numpy.linspace(0, endpoint, n_points + 1)
        return numpy.average(numpy.histogram(
            self._tags[tag][_START_TIME], bins)[0])

    def get_mean_ms_per_ts(self, tag, machine_time_step_ms):
        """ Get the mean time in milliseconds spent on operations with the\
            given tag per timestep

        :param tag: The tag to get the data for
        :type tag: str
        :param machine_time_step_ms:\
            The time step of the simulation in microseconds
        :type machine_time_step_ms: int
        :rtype: float
        """
        n_points = math.ceil(
            self._max_time / machine_time_step_ms)
        endpoint = n_points * machine_time_step_ms
        bins = numpy.linspace(0, endpoint, n_points + 1)
        mean_per_ts = scipy.stats.binned_statistic(
            self._tags[tag][_START_TIME], self._tags[tag][_DURATION],
            "mean", bins).statistic
        mean_per_ts[numpy.isnan(mean_per_ts)] = 0
        return numpy.average(
            mean_per_ts[numpy.logical_not(numpy.isnan(mean_per_ts))])
