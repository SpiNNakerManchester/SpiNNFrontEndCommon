from pacman.operations.pacman_algorithm_executor import PACMANAlgorithmExecutor
from pacman.utilities.utility_objs.progress_bar import ProgressBar

from spinn_front_end_common.interface import interface_functions
from spinn_front_end_common.interface.buffer_management.buffer_models.\
    abstract_receive_buffers_to_host import \
    AbstractReceiveBuffersToHost

import os
import math
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class FrontEndCommonAutoPauseAndResumer(object):
    """
    FrontEndCommonAutoPauseAndResumer: system that automatically allocate
    bandwidth resources and deduces what pause and resume functions are needed,
    and executes them accordingly
    """

    def __call__(
            self, partitioned_graph, runtime, wait_on_confirmation,
            send_start_notification, machine, notification_interface, app_id,
            txrx, time_scale_factor, loaded_reverse_iptags_token,
            loaded_iptags_token, loaded_routing_tables_token, graph_mapper,
            no_sync_changes, partitionable_graph, app_data_folder, verify,
            algorithms_to_run_between_runs, extra_inputs, extra_xmls,
            algorithm_for_dsg_generation, algorithm_for_dse_execution,
            machine_time_step, placements, tags, reports_states, routing_infos,
            has_ran_before, has_reset_before, application_graph_changed,
            steps=None):

        if steps is None:
            steps = self._deduce_number_of_iterations(
                placements, machine, runtime, machine_time_step)
        else:
            steps = self._generate_steps(runtime, machine_time_step, steps[0])

        if len(steps) != 1:
            logger.warn(
                "The simulation required more SDRAM for recording purposes"
                " than what was available. Therefore the system deduced that"
                " it needs to run the simulation in {} chunks, where the "
                "chunks of time consists of {}. If this is not suitable for "
                "your usage, please turn off use_auto_pause_and_resume in "
                " your config file. Thank you".format(len(steps), steps))

        inputs, first_algorithms, optional_algorithms, outputs, xmls = \
            self._setup_pacman_executor_inputs(
                wait_on_confirmation, partitionable_graph,
                send_start_notification, notification_interface, app_id, txrx,
                time_scale_factor, loaded_reverse_iptags_token,
                loaded_iptags_token, loaded_routing_tables_token,
                no_sync_changes, extra_inputs,
                extra_xmls, algorithm_for_dsg_generation,
                algorithm_for_dse_execution, tags, reports_states,
                app_data_folder, verify, routing_infos, placements,
                graph_mapper, partitioned_graph, machine, has_ran_before,
                has_reset_before, application_graph_changed)

        no_sync_changes, executable_targets, dsg_targets, buffer_manager, \
            processor_to_app_data_base_address, \
            placement_to_application_data_files, total_time = \
            self._execute_pacman_system_number_of_iterations(
                steps, inputs, first_algorithms, optional_algorithms,
                algorithms_to_run_between_runs, outputs, xmls)

        return {
            "RanToken": True,
            "no_sync_changes": no_sync_changes,
            "executable_targets": executable_targets,
            "dsg_targets": dsg_targets,
            "buffer_manager": buffer_manager,
            "processor_to_app_data_base_address":
                processor_to_app_data_base_address,
            "placement_to_app_data_files":
                placement_to_application_data_files,
            "LoadedApplicationDataToken": True,
            "LoadBinariesToken": True,
            "steps": steps,
            "total_time": total_time
        }

    def _deduce_number_of_iterations(
            self, placements, machine, runtime, machine_time_step):

        # Go through the placements and find how much SDRAM is available
        # on each chip
        sdram_tracker = dict()
        vertex_by_chip = defaultdict(list)
        for placement in placements.placements:
            vertex = placement.subvertex
            if isinstance(vertex, AbstractReceiveBuffersToHost):
                resources = vertex.resources_required
                if (placement.x, placement.y) not in sdram_tracker:
                    sdram_tracker[placement.x, placement.y] = \
                        machine.get_chip_at(
                            placement.x, placement.y).sdram.size
                sdram = (
                    resources.sdram.get_value() -
                    vertex.get_minimum_buffer_sdram_usage())
                sdram_tracker[placement.x, placement.y] -= sdram
                vertex_by_chip[placement.x, placement.y].append(vertex)

        # Go through the chips and divide up the remaining SDRAM, finding
        # the minimum number of machine timesteps to assign
        min_time_steps = None
        for x, y in vertex_by_chip:
            vertices_on_chip = vertex_by_chip[x, y]
            sdram = sdram_tracker[x, y]
            sdram_per_vertex = int(sdram / len(vertices_on_chip))
            for placement in vertices_on_chip:
                n_time_steps = vertex.get_n_timesteps_in_buffer_space(
                    sdram_per_vertex)
                if min_time_steps is None or n_time_steps < min_time_steps:
                    min_time_steps = n_time_steps

        return self._generate_steps(runtime, machine_time_step, min_time_steps)

    @staticmethod
    def _generate_steps(runtime, machine_time_step, min_machine_time_steps):

        total_no_machine_time_steps = int(math.ceil(
            (float(runtime) * 1000.0) / float(machine_time_step)))
        number_of_full_iterations = int(
            total_no_machine_time_steps / min_machine_time_steps)
        left_over_time_steps = int(
            total_no_machine_time_steps -
            (number_of_full_iterations * min_machine_time_steps))

        steps = [int(min_machine_time_steps)] * number_of_full_iterations
        if left_over_time_steps != 0:
            steps.append(int(left_over_time_steps))
        return steps

    def _setup_pacman_executor_inputs(
            self, wait_on_confirmation, partitionable_graph,
            send_start_notification, notification_interface, app_id, txrx,
            time_scale_factor, loaded_reverse_iptags_token,
            loaded_iptags_token, loaded_routing_tables_token, no_sync_changes,
            extra_inputs, extra_xmls, algorithm_for_dsg_generation,
            algorithm_for_dse_execution, tags, reports_states, app_data_folder,
            verify, routing_infos, placements, graph_mapper, partitioned_graph,
            machine, has_ran_before, has_reset_before,
            application_graph_changed):
        """

        :param wait_on_confirmation:
        :param partitionable_graph:
        :param send_start_notification:
        :param notification_interface:
        :param app_id:
        :param txrx:
        :param time_scale_factor:
        :param loaded_reverse_iptags_token:
        :param loaded_iptags_token:
        :param loaded_routing_tables_token:
        :param no_sync_changes:
        :param extra_inputs:
        :param extra_xmls:
        :param algorithm_for_dsg_generation:
        :param algorithm_for_dse_execution:
        :param tags;
        :param reports_states:
        :param app_data_folder:
        :param verify:
        :param routing_infos:
        :param placements:
        :param graph_mapper:
        :param partitioned_graph:
        :param machine:
        :return:
        """

        inputs = list()
        outputs = list()
        xmls = self.sort_out_xmls(extra_xmls)
        first_algorithms = list()
        optimal_algorithms = list()

        # standard algorithms needed for multi-runs before updater
        # (expected order here for debug purposes)
        first_algorithms.append("FrontEndCommonMachineTimeStepUpdater")
        if ((not has_ran_before and not has_reset_before) or
                application_graph_changed):
            # needs a dsg rebuild
            first_algorithms.append(algorithm_for_dsg_generation)
            first_algorithms.append(algorithm_for_dse_execution)
            optimal_algorithms.append("FrontEndCommonApplicationDataLoader")
            first_algorithms.append("FrontEndCommonLoadExecutableImages")
            first_algorithms.append("FrontEndCommonBufferManagerCreater")

        # handle outputs
        # TODO is this all i need here????
        outputs.append("RanToken")

        # handle inputs
        inputs.extend(extra_inputs)
        inputs.append({
            'type': 'WriteCheckerFlag',
            'value': verify})
        inputs.append({
            'type': "DatabaseWaitOnConfirmationFlag",
            'value': wait_on_confirmation})
        inputs.append({
            'type': "MemoryPartitionableGraph",
            'value': partitionable_graph})
        inputs.append({
            'type': "SendStartNotifications",
            'value': send_start_notification})
        inputs.append({
            'type': "NotificationInterface",
            'value': notification_interface})
        inputs.append({
            'type': "APPID",
            'value': app_id})
        inputs.append({
            'type': "MemoryTransciever",
            'value': txrx})
        inputs.append({
            'type': "TimeScaleFactor",
            'value': time_scale_factor})
        inputs.append({
            'type': "LoadedReverseIPTagsToken",
            'value': loaded_reverse_iptags_token})
        inputs.append({
            'type': "LoadedIPTagsToken",
            'value': loaded_iptags_token})
        inputs.append({
            'type': "LoadedRoutingTablesToken",
            'value': loaded_routing_tables_token})
        inputs.append({
            'type': "NoSyncChanges",
            'value': no_sync_changes})
        inputs.append({
            'type': "MemoryTags",
            'value': tags})
        inputs.append({
            'type': "ReportStates",
            'value': reports_states})
        inputs.append({
            'type': "ApplicationDataFolder",
            'value': app_data_folder})
        inputs.append({
            'type': "MemoryRoutingInfos",
            'value': routing_infos})
        inputs.append({
            "type": "MemoryPlacements",
            'value': placements})
        inputs.append({
            'type': "MemoryGraphMapper",
            'value': graph_mapper})
        inputs.append({
            'type': "MemoryPartitionedGraph",
            'value': partitioned_graph})
        inputs.append({
            'type': "MemoryExtendedMachine",
            'value': machine})

        return inputs, first_algorithms, optimal_algorithms, outputs, xmls

    @staticmethod
    def sort_out_xmls(extra_xmls):
        """

        :param extra_xmls:
        :return:
        """

        xmls = list()
        # add the extra XMLs
        xmls.extend(extra_xmls)

        # check that the front end common xml has been put in, if not, put in
        front_end_common_interface = \
            os.path.join(os.path.dirname(interface_functions.__file__),
                         "front_end_common_interface_functions.xml")
        found = False
        for xml_path in xmls:
            if xml_path == front_end_common_interface:
                found = True
        if not found:
            xmls.append(front_end_common_interface)
        return xmls

    def _execute_pacman_system_number_of_iterations(
            self, steps, inputs, first_algorithms, optimal_algorithms,
            algorithms_to_run_between_runs, outputs, xmls):
        """

        :param inputs:
        :param first_algorithms:
        :param outputs:
        :param optimal_algorithms:
        :param xmls:
        :param algorithms_to_run_between_runs:
        :return:
        """
        pacman_executor = None
        for iteration in range(0, len(steps)):
            # during each iteration, you need to run:
            # application runner, no_machine_time_steps_updater,
            # EXTRA_ALGORITHMS, runtime_updater
            self._update_inputs(pacman_executor, inputs, steps, iteration)

            # if its the first iteration, do all the boiler plate of DSG, DSE,
            # app data load, executable load, etc
            if iteration == 0:
                all_algorithms = list(first_algorithms)
                if len(steps) != 1:
                    all_algorithms.append("FrontEndCommonRuntimeUpdater")
                    all_algorithms.append("FrontEndCommonApplicationRunner")
                    all_algorithms.extend(algorithms_to_run_between_runs)
                else:
                    all_algorithms.append("FrontEndCommonApplicationRunner")
            else:
                all_algorithms = list()
                all_algorithms.extend(algorithms_to_run_between_runs)
                all_algorithms.append("FrontEndCommonMachineTimeStepUpdater")
                all_algorithms.append("FrontEndCommonRuntimeUpdater")
                all_algorithms.append("FrontEndCommonApplicationRunner")

            # create and execute
            pacman_executor = PACMANAlgorithmExecutor(
                algorithms=all_algorithms, inputs=inputs, xml_paths=xmls,
                required_outputs=outputs,
                optional_algorithms=optimal_algorithms)
            pacman_executor.execute_mapping()

        return pacman_executor.get_item("NoSyncChanges"), \
            pacman_executor.get_item("ExecutableTargets"), \
            pacman_executor.get_item("DataSpecificationTargets"), \
            pacman_executor.get_item("BufferManager"), \
            pacman_executor.get_item("ProcessorToAppDataBaseAddress"), \
            pacman_executor.get_item("PlacementToAppDataFilePaths"), \
            pacman_executor.get_item("TotalCommunitiveRunTime")

    def _update_inputs(self, pacman_executor, inputs, steps, iteration):
        """

        :param pacman_executor:
        :param inputs:
        :param steps:
        :param iteration:
        :return:
        """
        if pacman_executor is not None:
            old_inputs = pacman_executor.get_items()
            for item in old_inputs:
                # extraction from run
                self._update_input_variable(
                    inputs, item, variable=old_inputs[item])

        self._update_input_variable(
            inputs, "RunTime", pacman_executor, steps[iteration])
        self._update_input_variable(
            inputs, "Steps", pacman_executor, steps)
        self._update_input_variable(
            inputs, "Iteration", pacman_executor, iteration)

    def _update_input_variable(
            self, inputs, variable_name, pacman_executor=None, variable=None):
        parameter_index = self._locate_index_of_input(inputs, variable_name)
        if parameter_index is not None and variable is not None:
            inputs[parameter_index] = {
                'type': variable_name,
                'value': variable}
        elif parameter_index is None and variable is not None:
            inputs.append({
                'type': variable_name,
                'value': variable
            })
        elif parameter_index is None and variable is None:
            inputs.append({
                'type': variable_name,
                'value': pacman_executor.get_item(variable_name)
            })
        elif parameter_index is not None and variable is None:
            inputs[parameter_index] = {
                'type': variable_name,
                'value': pacman_executor.get_item(variable_name)}

    @staticmethod
    def _locate_index_of_input(inputs, type_name):
        """

        :param inputs:
        :param type_name:
        :return:
        """
        index = 0
        found = False
        while not found and index < len(inputs):
            current_input = inputs[index]
            if current_input['type'] == type_name:
                found = True
            else:
                index += 1
        if not found:
            return None
        return index


# TODO There must be a way to remove this requirement, but not sure how yet.
class FrontEndCommonMachineTimeStepUpdater(object):

    def __call__(self, iteration, steps, total_run_time_executed_so_far,
                 partitionable_graph):

        progress_bar = ProgressBar(
            len(partitionable_graph.vertices),
            "Updating python runtime in machine time steps")

        # deduce the new runtime position
        set_runtime = total_run_time_executed_so_far
        set_runtime += steps[iteration]

        # update the partitionable vertices
        for vertex in partitionable_graph.vertices:
            vertex.set_no_machine_time_steps(set_runtime)
            progress_bar.update()
        progress_bar.end()

        return {"runtime_in_machine_time_steps": set_runtime}
