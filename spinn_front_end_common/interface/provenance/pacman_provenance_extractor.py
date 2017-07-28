from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem


class PacmanProvenanceExtractor(object):
    """ Extracts Provenance data from a PACMANAlgorithmExecutor
    """

    def __init__(self):
        self._data_items = list()

    def extract_provenance(self, executor):
        """ acquires the timings from pacman algorithms (provenance data)

        :param executor: the pacman workflow executor
        :rtype: None
        """
        for (algorithm, run_time, exec_names) in executor.algorithm_timings:
            names = ["pacman"]
            names.append(exec_names)
            names.extend(["run_time_of_{}".format(algorithm)])
            self._data_items.append(ProvenanceDataItem(names, run_time))

    @property
    def data_items(self):
        """ returns the provenance data items

        :return: list of provenance data items.
        :rtype: iterable of ProvenanceDataItem
        """
        return self._data_items

    def clear(self):
        """ clears the provenance data store

        :rtype: None
        """
        self._data_items = list()
