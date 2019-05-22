

class BitFieldSummary(object):

    def __init__(self, total_merged, max_per_chip, lowest_per_chip):
        self._total_merged = total_merged
        self._max_per_chip = max_per_chip
        self._lowest_per_chip = lowest_per_chip

    @property
    def total_merged(self):
        return self._total_merged

    @property
    def max_per_chip(self):
        return self._max_per_chip

    @property
    def lowest_per_chip(self):
        return
