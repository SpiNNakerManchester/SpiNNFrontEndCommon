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

import os
from spinn_utilities.executable_finder import ExecutableFinder as BaseEF
from spinn_front_end_common import common_model_binaries


class ExecutableFinder(BaseEF):
    """ Manages a set of folders in which to search for binaries, and allows\
        for binaries to be discovered within this path. This adds a default\
        location to look to the base class.
    """

    def __init__(self, binary_search_paths=None,
                 include_common_binaries_folder=True):
        """
        :param binary_search_paths: \
            The initial set of folders to search for binaries.
        :type binary_search_paths: iterable of str
        :param include_common_binaries_folder: \
            If True (i.e. the default), the \
            spinn_front_end_common.common_model_binaries folder is searched\
            for binaries.  If you are not using the common models, or the\
            model binary names conflict with your own, this parameter can be\
            used to avoid this issue. Note that the folder will be appended\
            to the value of binary_search_paths, so the common binary search\
            path will be looked in last.
        :type include_common_binaries_folder: bool
        """
        if binary_search_paths is None:
            binary_search_paths = list()
        super(ExecutableFinder, self).__init__(binary_search_paths)
        if include_common_binaries_folder:
            self.add_path(os.path.dirname(common_model_binaries.__file__))
