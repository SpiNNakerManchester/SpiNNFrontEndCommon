# Copyright (c) 2020-2021 The University of Manchester
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

from .splitter_slice_legacy import SplitterSliceLegacy
from .splitter_per_chip_legacy import SplitterPerChipLegacy
from .splitter_per_ethernet_chip_legacy import SplitterPerEthernetChipLegacy
from .splitter_one_to_one_legacy import SplitterOneToOneLegacy
from .splitter_fixed_slice_size import SplitterFixedSliceSized

__all__ = [
    'SplitterFixedSliceSized', 'SplitterOneToOneLegacy',
    'SplitterSliceLegacy', 'SplitterPerChipLegacy',
    'SplitterPerEthernetChipLegacy']