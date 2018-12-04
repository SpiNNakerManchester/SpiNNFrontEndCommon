from .data_row_writer import DataRowWriter


class DataSpecificationTargets(object):

    def __init__(self):
        self._temp = dict()

    def create_data_spec(self, x, y, p):
        return DataRowWriter(x, y, p, self)

    def write(self, x, y, p, data):
        self._temp[(x, y, p)] = data
