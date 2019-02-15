from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem


class PacmanProvenanceExtractor(object):
    """ Extracts Provenance data from a :py:class:`PACMANAlgorithmExecutor`
    """

    def __init__(self):
        self._data_items = list()

    def extract_provenance(self, executor):
        """ Acquires the timings from PACMAN algorithms (provenance data)

        :param executor: the PACMAN workflow executor
        :rtype: None
        """
        for (algorithm, run_time, exec_names) in executor.algorithm_timings:
            names = ["pacman"]
            names.append(exec_names)
            names.extend(["run_time_of_{}".format(algorithm)])
            self._data_items.append(ProvenanceDataItem(names, run_time))

    @property
    def data_items(self):
        """ Returns the provenance data items

        :return: list of provenance data items.
        :rtype: iterable(:py:class:`ProvenanceDataItem`)
        """
        return self._data_items

    def clear(self):
        """ Clears the provenance data store

        :rtype: None
        """
        self._data_items = list()
