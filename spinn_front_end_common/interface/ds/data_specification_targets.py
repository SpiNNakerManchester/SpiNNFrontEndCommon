from six import iteritems
from .data_row_writer import DataRowWriter
from .data_row_reader import DataRowReader


class DataSpecificationTargets(object):

    def __init__(self):
        self._temp = dict()

    def create_data_spec(self, x, y, p):
        return DataRowWriter(x, y, p, self)

    def write(self, x, y, p, data):
        self._temp[(x, y, p)] = data

    def n_targets(self):
        return len(self._temp)

    def iteritems(self):
         for key, value in iteritems(self._temp):
             yield key, DataRowReader(value)
