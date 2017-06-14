import numpy
import logging

logger = logging.getLogger(__name__)

# Define profiler time scale
_MS_SCALE = (1.0 / 200032.4)

# Define the positions in tags
_START_TIME = 0
_DURATION = 1


class ProfileData(object):
    """ A container for profile data
    """

    START_TIME = 0
    DURATION = 1

    __slots__ = (

        # A dictionary of tag label to numpy array of start times and durations
        "_tags",

        # A list of tag labels indexed by the tag id
        "_tag_labels",

        # The machine time step in milliseconds
        "_machine_time_step_ms",

        # The run time in milliseconds
        "_run_time_ms"
    )

    def __init__(self, tag_labels, machine_time_step, run_time_ms):
        """

        :param tag_labels: A list of labels indexed by tag id
        :type tag_labels: list(str)
        :param machine_time_step:\
            The time step of the simulation in microseconds
        :type machine_time_step: int
        :param run_time_ms: The run time of the simulation in milliseconds
        :type run_time_ms: float
        """
        self._tag_labels = tag_labels
        self._machine_time_step_ms = (float(machine_time_step) / 1000.0)
        self._run_time_ms = float(run_time_ms)
        self._tags = dict()

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
        sample_times = numpy.subtract(sample_times[0], sample_times)
        sample_times_ms = numpy.multiply(
            sample_times, _MS_SCALE, dtype=numpy.float)

        # Slice tags and times into entry and exits
        entry_tags = sample_tags[sample_entry_indices]
        entry_times_ms = sample_times_ms[sample_entry_indices]
        exit_tags = sample_tags[sample_exit_indices]
        exit_times_ms = sample_times_ms[sample_exit_indices]

        # Loop through unique tags
        unique_tags = numpy.unique(sample_tags)
        for tag in unique_tags:

            tag_label = self._tag_labels.get(tag, None)
            if tag_label is None:
                logger.warn("Unknown tag {} in profile data".format(tag))
                tag_label = "UNKNOWN"

            # Get indices where these tags occur
            tag_entry_indices = numpy.where(entry_tags == tag)
            tag_exit_indices = numpy.where(exit_tags == tag)

            # Use these to get subset for this tag
            tag_entry_times_ms = entry_times_ms[tag_entry_indices]
            tag_exit_times_ms = exit_times_ms[tag_exit_indices]

            # If the first exit is before the first
            # Entry, add a dummy entry at beginning
            if tag_exit_times_ms[0] < tag_entry_times_ms[0]:
                logger.warn("Profile starts mid-tag")
                tag_entry_times_ms = numpy.append(0.0, tag_entry_times_ms)

            if len(tag_entry_times_ms) > len(tag_exit_times_ms):
                logger.warn("profile finishes mid-tag")
                tag_entry_times_ms = tag_entry_times_ms[
                    :len(tag_exit_times_ms) - len(tag_entry_times_ms)]

            # Subtract entry times from exit times to get durations of each
            # call
            tag_durations_ms = numpy.subtract(
                tag_exit_times_ms, tag_entry_times_ms)

            # Add entry times and durations to dictionary
            self._tags[tag_label] = (tag_entry_times_ms, tag_durations_ms)

    @property
    def tags(self):
        """ The tags recorded as labels

        :rtype: list of str
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

    def get_mean_n_calls_per_ts(self, tag):
        """ Get the mean number of times the given tag was recorded per\
            timestep

        :param tag: The tag to get the data for
        :type tag: str
        :rtype: float
        """
        n_bins = self._run_time_ms / self._machine_time_step_ms
        return numpy.average(numpy.histogram(
            self._tags[tag][_START_TIME], n_bins)[0])

    def get_mean_ms_per_ts(self, tag):
        """ Get the mean time in milliseconds spent on operations with the\
            given tag per timestep

        :param tag: The tag to get the data for
        :type tag: str
        :rtype: float
        """
        bins = numpy.arange(0, self._run_time_ms, self._machine_time_step_ms)
        bin_positions = numpy.digitize(self._tags[tag][_START_TIME], bins)
        binned_durations = self._tags[tag][_DURATION][bin_positions]
        return numpy.average(numpy.sum(binned_durations, axis=1))

    def print_stats(self):
        """ Print a summary of profile data
        """
        print "{: <10s} {: <7s} {: <7s} {: <14s} {: <14s}".format(
            "tag", "n_calls", "mean_ms", "n_calls_per_ts", "mean_ms_per_ts")
        print "{:-<10s} {:-<7s} {:-<7s} {:-<14s} {:-<14s}".format(
            "", "", "", "", "")
        for tag in self.tags:
            print "{: <10s} {: >7d} {: >7.2f} {: >14.2f} {: >14.2f}".format(
                tag, self.get_n_calls(tag), self.get_mean_ms(tag),
                self.get_mean_n_calls_per_ts(tag),
                self.get_mean_ms_per_ts(tag))
