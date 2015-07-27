from spinn_front_end_common.utilities import exceptions
from spinnman.model.core_subsets import CoreSubsets


class ExecutableTargets(object):
    """
    obejct to encapsulate the binaries and coresets in an object for
    interface usages
    """

    def __init__(self):
        self._targets = dict()
        self._total_processors = 0
        self._need_to_create_subset_list = True
        self._core_subsets = list()

    def add_binary(self, binary):
        """
        adds a binary path to the list of exeuctables with a blank list of
         processors
        :param binary:
        :return:
        """
        if binary not in self._targets:
            self._targets[binary] = CoreSubsets()
        else:
            raise exceptions.ConfigurationException(
                "cant add a binary thats already been added.")

    def has_binary(self, binary):
        """
        returns true if the binary naem is already in the list of executable
        targets
        :param binary:
        :return: boolean which si true if exists, false otherwise
        """
        return binary in self._targets

    def add_subsets(self, binary, subsets):
        """
        adds a subset to a binary
        :param binary: the path to the binary needed to be exeucted
        :param subsets: the subset of cores that the binary needs to be loaded\
                    on
        :return:
        """
        if self.has_binary(binary):
            self._targets[binary].add_core_subset(subsets)
        else:
            self._targets[binary] = subsets
        for subset in subsets.core_subsets:
            for _ in subset.processor_ids:
                self._total_processors += 1

    def add_processor(self, binary, chip_x, chip_y, chip_p):
        """
        adds a processor to the executable targets
        :param binary: the binary path for executable
        :param chip_x: the coordinate on the machine in terms of x for the chip
        :param chip_y: the coordinate on the machine in terms of y for the chip
        :param chip_p: the processor id to place this executable on
        :return:
        """
        if self.has_binary(binary):
            self._targets[binary].add_processor(chip_x, chip_y, chip_p)
        else:
            self.add_binary(binary)
            self._targets[binary].add_processor(chip_x, chip_y, chip_p)
        self._total_processors += 1
        self._need_to_create_subset_list = True

    def retrieve_cores_for_a_executable_target(self, binary):
        """ from a binary name, retrieves the core subsets associated with it

        :param binary:
        :return:
        """
        if self.has_binary(binary):
            return self._targets[binary]
        else:
            return None

    def binary_paths(self):
        """
        retrusn the binaries paths required from these exeuctables.
        :return:
        """
        return self._targets.keys()

    @property
    def total_processors(self):
        """
        property for the total number of processors which need executables
        :return:
        """
        return self._total_processors

    @property
    def all_core_subsets(self):
        """
        iterates though all the core subsets and returns a list of them all,
        no matter which executable binary is running on them.
        :return:
        """
        if self._need_to_create_subset_list:
            # clear the list in case others have been added since
            del self._core_subsets[:]
            for executable_target in self._targets:
                core_subsets = self._targets[executable_target]
                for core_subset in core_subsets:
                    for _ in core_subset.processor_ids:
                        self._core_subsets.append(core_subset)
        return self._core_subsets
