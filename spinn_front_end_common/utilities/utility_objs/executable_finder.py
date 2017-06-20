import os
from spinn_utilities.executable_finder import ExecutableFinder as BaseEF
from spinn_front_end_common import common_model_binaries


class ExecutableFinder(BaseEF):
    """ Manages a set of folders in which to search for binaries,
        and allows for binaries to be discovered within this path.
        This adds a default location to look to the base class.
    """

    def __init__(self, binary_search_paths=None,
                 include_common_binaries_folder=True):
        """

        :param binary_search_paths: The initial set of folders to search for\
                    binaries.
        :type binary_search_paths: iterable of str
        :param include_common_binaries_folder: If True (i.e. the default), \
                    the spinn_front_end_common.common_model_binaries folder \
                    is searched for binaries.  If you are not using the common\
                    models, or the model binary names conflict with your own,\
                    this parameter can be used to avoid this issue.  Note that\
                    the folder will be appended to the value of\
                    binary_search_paths, so the common binary search path will\
                    be looked in last.
        :type include_common_binaries_folder: bool
        """
        if binary_search_paths is None:
            binary_search_paths = list()
        BaseEF.__init__(self, binary_search_paths)
        if include_common_binaries_folder:
            self.add_path(os.path.dirname(
                common_model_binaries.__file__))
