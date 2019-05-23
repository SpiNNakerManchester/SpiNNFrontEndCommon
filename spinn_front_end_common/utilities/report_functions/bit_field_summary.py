

class BitFieldSummary(object):

    def __init__(
            self, total_merged, max_per_chip, lowest_per_chip, total_to_merge,
            max_to_merge_per_chip, low_to_merge_per_chip,
            average_per_chip_merged, average_per_chip_to_merge):
        self._total_merged = total_merged
        self._max_per_chip = max_per_chip
        self._lowest_per_chip = lowest_per_chip
        self._total_to_merge = total_to_merge
        self._max_to_merge_per_chip = max_to_merge_per_chip
        self._low_to_merge_per_chip = low_to_merge_per_chip
        self._average_per_chip_merged = average_per_chip_merged
        self._average_per_chip_to_merge = average_per_chip_to_merge

    @property
    def total_merged(self):
        return self._total_merged

    @property
    def max_per_chip(self):
        return self._max_per_chip

    @property
    def lowest_per_chip(self):
        return self._lowest_per_chip

    @property
    def total_to_merge(self):
        return self._total_to_merge

    @property
    def max_to_merge_per_chip(self):
        return self._max_to_merge_per_chip

    @property
    def low_to_merge_per_chip(self):
        return self._low_to_merge_per_chip

    @property
    def average_per_chip_merged(self):
        return self._average_per_chip_merged

    @property
    def average_per_chip_to_merge(self):
        return self._average_per_chip_to_merge

