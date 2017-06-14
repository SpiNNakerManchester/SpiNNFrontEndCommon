# spinn front end common imports
from spinn_front_end_common.utility_models.\
    chip_power_monitor_application_vertex import \
    ChipPowerMonitorApplicationVertex
from spinn_front_end_common.utility_models.\
    chip_power_monitor_machine_vertex import ChipPowerMonitorMachineVertex

# pacman imports
from pacman.model.graphs.common.slice import Slice
from pacman.model.constraints.placer_constraints\
    .placer_chip_and_core_constraint import PlacerChipAndCoreConstraint

# utils imports
from spinn_utilities.progress_bar import ProgressBar


class FrontEndCommonInsertChipPowerMonitorsToGraphs(object):
    """ function to add chip power monitors into a given graph
    """

    def __call__(
            self, machine, machine_graph, n_samples_per_recording,
            sampling_frequency, application_graph=None, graph_mapper=None):
        """ call that adds LPG vertices on Ethernet connected chips as\
            required.

        :param machine: the spinnaker machine as discovered
        :param application_graph: the application graph
        :param machine_graph: the machine graph
        :return: mapping between LPG params and LPG vertex
        """

        # create progress bar
        progress_bar = ProgressBar(
            len(machine.chips),
            string_describing_what_being_progressed=(
                "Adding Chip power monitors to Graph"))

        for chip in progress_bar.over(machine.chips()):
            constraint = PlacerChipAndCoreConstraint(chip.x, chip.y)
            machine_vertex = ChipPowerMonitorMachineVertex(
                label="chip_power_monitor_machine_vertex_for_chip({}:{})".
                    format(chip.x, chip.y),
                sampling_frequency=sampling_frequency,
                n_samples_per_recording=n_samples_per_recording,
                constraints=[constraint])

            if application_graph is not None:
                vertex_slice = Slice(0, 0)
                application_vertex = \
                    ChipPowerMonitorApplicationVertex(
                        label="chip_power_monitor_application_vertex_for"
                              "_chip({}:{})".format(chip.x, chip.y),
                        constraints=[constraint],
                        sampling_frequency=sampling_frequency,
                        n_samples_per_recording=n_samples_per_recording)
                application_graph.add_vertex(application_vertex)
                graph_mapper.add_vertex_mapping(
                    machine_vertex, vertex_slice, application_vertex)

            # update progress bar
            progress_bar.update()

        # update progress bar
        progress_bar.end()
