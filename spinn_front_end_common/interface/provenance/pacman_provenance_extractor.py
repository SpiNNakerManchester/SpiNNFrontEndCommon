from spinn_front_end_common.utilities.utility_objs.provenance_data_item \
    import ProvenanceDataItem


class PacmanProvenanceExtractor(object):
    """ Extracts Provenance data from a PACMANAlgorithmExecutor
    """

    def __init__(self):
        self._data_items = list()

    def extract_provenance(self, executor):
        for (algorithm, run_time) in executor.algorithm_timings:
            names = ["pacman", "run_time_of_{}".format(algorithm)]
            self._data_items.append(ProvenanceDataItem(names, str(run_time)))

    @property
    def data_items(self):
        return self._data_items

    def clear(self):
        self._data_items = list()
