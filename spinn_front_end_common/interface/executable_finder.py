import os
from spinn_front_end_common import common_model_binaries


class ExecutableFinder(object):
    """ Manages a set of folders in which to search for binaries,
        and allows for binaries to be discovered within this path
    """

    def __init__(self, binary_search_paths=None,
                 include_common_binaries_folder=True):
        """

        :param binary_search_paths: The initial set of folders to search for\
                    binaries.
        :type binary_search_paths: array of str
        :param include_common_binaries_folder: If True (i.e. the default), \
                    the spinn_front_end_common.common_model_binaries folder \
                    is searched for binaries.  If you are not using the common\
                    models, or the model binary names conflict with your own,\
                    this parameter can be used to avoid this issue.  Note that\
                    the folder will be appended to the value of\
                    binary_search_paths, so the common binary search path will\
                    be looked in last.
        """
        if binary_search_paths is None:
            binary_search_paths = list()
        self._binary_search_paths = binary_search_paths
        if include_common_binaries_folder:
            self._binary_search_paths.append(os.path.dirname(
                common_model_binaries.__file__))

    def add_path(self, path):
        """ Adds a path to the set of folders to be searched.  The path is\
            added to the end of the list, so it is searched after all the\
            paths currently in the list.

        :param path: The path to add
        :type path: str
        :return: Nothing is returned
        :rtype: None
        """
        self._binary_search_paths.append(path)

    def get_executable_path(self, executable_name):
        """ Finds an executable within the set of folders.  The set of folders\
            is searched sequentially and the first match is returned.

        :param executable_name: The name of the executable to find
        :type executable_name: str
        :return: The full path of the discovered executable, or None if no \
                    executable was found in the set of folders
        :rtype: str
        """

        # Loop through search paths
        for path in self._binary_search_paths:

            # Rebuild filename
            potential_filename = os.path.join(path, executable_name)

            # If this filename exists, return it
            if os.path.isfile(potential_filename):
                return potential_filename

        # No executable found
        return None
