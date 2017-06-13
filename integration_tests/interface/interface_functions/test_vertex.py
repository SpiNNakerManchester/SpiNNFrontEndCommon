
"""
test vertex used in many unit tests
"""

# pacman imports

from pacman.model.graphs.application import ApplicationVertex
from pacman.model.resources import DTCMResource, ResourceContainer, \
    SDRAMResource, CPUCyclesPerTickResource
from pacman.model.graphs.machine import SimpleMachineVertex
from pacman.model.decorators.overrides import overrides


class TestVertex(ApplicationVertex):
    """
    test vertex
    """
    _model_based_max_atoms_per_core = None

    def __init__(self, n_atoms, label="testVertex", max_atoms_per_core=256,
                 constraints=None, fixed_sdram_value=None):
        ApplicationVertex.__init__(
            self, label=label, max_atoms_per_core=max_atoms_per_core,
            constraints=constraints)
        self._model_based_max_atoms_per_core = max_atoms_per_core
        self._n_atoms = n_atoms
        self._fixed_sdram_value = fixed_sdram_value

    def get_resources_used_by_atoms(self, vertex_slice):
        """
        standard method call to get the sdram, cpu and dtcm usage of a
        collection of atoms
        :param vertex_slice: the collection of atoms
        :return:
        """
        return ResourceContainer(
            sdram=SDRAMResource(
                self.get_sdram_usage_for_atoms(vertex_slice, None)),
            cpu_cycles=CPUCyclesPerTickResource(
                self.get_cpu_usage_for_atoms(vertex_slice, None)),
            dtcm=DTCMResource(
                self.get_dtcm_usage_for_atoms(vertex_slice, None)))

    def get_cpu_usage_for_atoms(self, vertex_slice, graph):
        """

        :param vertex_slice: the atoms being considered
        :param graph: the graph
        :return: the amount of cpu (in cycles this model will use)
        """
        return 1 * vertex_slice.n_atoms

    def get_dtcm_usage_for_atoms(self, vertex_slice, graph):
        """

        :param vertex_slice: the atoms being considered
        :param graph: the graph
        :return: the amount of dtcm (in bytes this model will use)
        """
        return 1 * vertex_slice.n_atoms

    def get_sdram_usage_for_atoms(self, vertex_slice, graph):
        """
        :param vertex_slice: the atoms being considered
        :param graph: the graph
        :return: the amount of sdram (in bytes this model will use)
        """
        if self._fixed_sdram_value is None:
            return 1 * vertex_slice.n_atoms
        else:
            return self._fixed_sdram_value

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(
            self, vertex_slice, resources_required, label=None,
            constraints=None):
        return SimpleMachineVertex(resources_required, label, constraints)

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return self._n_atoms
