from pacman.model.resources.cpu_cycles_per_tick_resource import \
    CPUCyclesPerTickResource
from pacman.model.resources.dtcm_resource import DTCMResource
from pacman.model.resources.resource_container import ResourceContainer
from pacman.model.resources.sdram_resource import SDRAMResource
from pacman.operations.pacman_algorithm_executor import PACMANAlgorithmExecutor
from pacman.utilities.utility_objs.progress_bar import ProgressBar
from pacman.utilities.utility_objs.resource_tracker import ResourceTracker

from spinn_front_end_common.interface import interface_functions
from spinn_front_end_common.interface.abstract_recordable_interface import \
    AbstractRecordableInterface
from spinn_front_end_common.interface.buffer_management.buffer_models.\
    abstract_receive_buffers_to_host import \
    AbstractReceiveBuffersToHost
from spinn_front_end_common.utility_models.\
    reverse_ip_tag_multicast_source_partitioned_vertex import \
    ReverseIPTagMulticastSourcePartitionedVertex
from spinn_front_end_common.utilities import exceptions

import os
import math
import sys
import logging

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
            time_theshold, steps=None):

        if steps is None:
            steps = self._deduce_number_of_iterations(
                partitioned_graph, runtime, time_scale_factor,
                machine, machine_time_step, placements, graph_mapper,
                partitionable_graph)
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
                has_reset_before, application_graph_changed, time_theshold)

        no_sync_changes, executable_targets, dsg_targets, buffer_manager, \
            processor_to_app_data_base_address, \
            placement_to_application_data_files, total_time = \
            self._execute_pacman_system_number_of_iterations(
                steps, inputs, first_algorithms, optional_algorithms,
                algorithms_to_run_between_runs, outputs, xmls)

        return {
            'RanToken': True, "no_sync_changes": no_sync_changes,
            'executable_targets': executable_targets,
            'dsg_targets': dsg_targets, "buffer_manager": buffer_manager,
            'processor_to_app_data_base_address':
            processor_to_app_data_base_address,
            'placement_to_app_data_files':
            placement_to_application_data_files,
            "LoadedApplicationDataToken": True, "LoadBinariesToken": True,
            'steps': steps, 'total_time': total_time
            }

    def _deduce_number_of_iterations(
            self, partitioned_graph, runtime, time_scale_factor,
            machine, machine_time_step, placements, graph_mapper,
            partitionable_graph):
        """

        :param partitioned_graph:
        :param runtime:
        :param time_scale_factor:
        :param machine:
        :param machine_time_step:
        :param placements:
        :param graph_mapper:
        :param partitionable_graph:
        :return:
        """

        bandwidth_resource = \
            self._deduce_ethernet_connected_chips_bandwidth_resource(
                machine_time_step, time_scale_factor, machine)

        # build resource tracker for sdram usage
        resource_tracker = ResourceTracker(machine)

        # allocate static sdram usage to the resource tracker, leaving us
        # with just the sdram available for runtime usage
        for vertex in partitioned_graph.subvertices:
            # remove bodge memory requirement if a AbstractReceiveBuffersToHost
            # vertex
            if isinstance(vertex, AbstractReceiveBuffersToHost):
                resources = ResourceContainer(
                    cpu=CPUCyclesPerTickResource(
                        vertex.resources_required.cpu.get_value()),
                    dtcm=DTCMResource(
                        vertex.resources_required.dtcm.get_value()),
                    sdram=SDRAMResource(
                        vertex.resources_required.sdram.get_value() -
                        vertex.extra_static_sdram_requirement()))
                resource_tracker.allocate_constrained_resources(
                    resources, vertex.constraints)
            else:
                resource_tracker.allocate_constrained_resources(
                    vertex.resources_required, vertex.constraints)

        # update all ethernet resources for
        # ReverseIPTagMulticastSourcePartitionedVertex's
        self._update_ethernet_bandwidth_off_injectors(
            bandwidth_resource, placements, machine, partitioned_graph)

        # turn off all buffered out for cores which reside on chips where there
        # ethernet connected chip has no bandwidth left, and allocate left overs
        self._turn_off_buffered_out_as_required(
            bandwidth_resource, placements, machine, graph_mapper,
            partitionable_graph)

        # locate whatever the min time step would be for all chips given
        # left over sdram
        min_machine_time_steps = \
            self._discover_min_time_steps_with_sdram_available(
                machine, placements, resource_tracker, graph_mapper,
                partitionable_graph)

        return self._generate_steps(
            runtime, machine_time_step, min_machine_time_steps)

    @staticmethod
    def _generate_steps(runtime, machine_time_step, min_machine_time_steps):

        # calculate the steps array
        total_no_machine_time_steps = (runtime * 1000) / machine_time_step

        number_of_full_iterations = \
            int(math.floor(
                total_no_machine_time_steps / min_machine_time_steps))
        left_over_time_steps = \
            int(total_no_machine_time_steps - (number_of_full_iterations *
                                               min_machine_time_steps))

        steps = list()
        for _ in range(0, number_of_full_iterations):
            steps.append(int(min_machine_time_steps))
        if left_over_time_steps != 0:
            steps.append(int(left_over_time_steps))
        return steps

    def _discover_min_time_steps_with_sdram_available(
            self, machine, placements, resource_tracker, graph_mapper,
            partitionable_graph):
        """

        :param placements:
        :param machine:
        :param resource_tracker:
        :return:
        """
        min_machine_time_steps = sys.maxint
        for chip in machine.chips:
            chip_placements = placements.get_placements_on_chip(chip.x, chip.y)
            none_buffered_placements = list()
            for chip_placement in chip_placements:
                if self._check_for_none_buffered_functionality(chip_placement):
                    none_buffered_placements.append(chip_placement)

            sdram_left_over = \
                resource_tracker.sdram_avilable_on_chip(chip.x, chip.y)

            this_chips_min_machine_time_steps = \
                self._calculate_min_machine_time_step_for_bunch_of_placements(
                    none_buffered_placements, sdram_left_over, graph_mapper,
                    partitionable_graph)

            if this_chips_min_machine_time_steps < min_machine_time_steps:
                min_machine_time_steps = this_chips_min_machine_time_steps

        return min_machine_time_steps

    @staticmethod
    def _check_for_none_buffered_functionality(chip_placement):

        # get params
        is_r_i_m_c_s = isinstance(
            chip_placement.subvertex,
            ReverseIPTagMulticastSourcePartitionedVertex)
        is_sending_buffers_to_host = isinstance(
            chip_placement.subvertex, AbstractReceiveBuffersToHost)
        is_recording_stuff = isinstance(
            chip_placement.subvertex, AbstractRecordableInterface)

        # do check
        if (not is_r_i_m_c_s and is_recording_stuff and
                (not is_sending_buffers_to_host) or
                is_sending_buffers_to_host):
            return True
        else:
            return False

    # overloadable method for optimisations on chip sdram distribution
    @staticmethod
    def _calculate_min_machine_time_step_for_bunch_of_placements(
            placements, sdram_left_over, graph_mapper, partitionable_graph):
        """

        :param placements:
        :param sdram_left_over:
        :param graph_mapper:
        :param partitionable_graph:
        :return:
        """
        # assuming shared equally, maybe optimisations for unbalanced usage
        min_chip_no_machine_time_steps = sys.maxint
        if len(placements) > 0:
            sdram_each = math.floor(sdram_left_over / len(placements))
            for placement in placements:

                # locate individual machine time step worth of sdram usage
                vertex_slice = graph_mapper.get_subvertex_slice(
                    placement.subvertex)
                vertex = graph_mapper.get_vertex_from_subvertex(
                    placement.subvertex)
                individual_machine_time_step_sdram_usage = \
                    vertex.get_runtime_sdram_usage_for_atoms(
                        vertex_slice, partitionable_graph, 1)
                
                if individual_machine_time_step_sdram_usage == 0:
                    no_machine_time_steps = sys.maxint
                else:
                    # calculate min sdram usage for shared sdram allocation
                    no_machine_time_steps = math.floor(
                        sdram_each / individual_machine_time_step_sdram_usage)

                # safety check
                expected_sdram_usage = \
                    vertex.get_runtime_sdram_usage_for_atoms(
                        vertex_slice, partitionable_graph,
                        no_machine_time_steps)
                if expected_sdram_usage > sdram_each:
                    raise exceptions.ConfigurationException(
                        "Have not been programmed to handle models which "
                        "change their requirements of sdram within a runtime. "
                        "Please fix and try again")

                # update min chip machine time steps accordingly
                if no_machine_time_steps < min_chip_no_machine_time_steps:
                    min_chip_no_machine_time_steps = no_machine_time_steps

        return min_chip_no_machine_time_steps

    def _turn_off_buffered_out_as_required(
            self, bandwidth_resource, placements, machine, graph_mapper,
            partitionable_graph):
        """

        :param bandwidth_resource:
        :param placements:
        :param machine:
        :param partitionable_graph:
        :return:
        """
        for (ethernet_connected_chip_x,
                ethernet_connected_chip_y) in bandwidth_resource:
            chips_in_region_of_ethernet = \
                machine.get_chips_via_local_ethernet(
                    ethernet_connected_chip_x, ethernet_connected_chip_y)
            for chip in chips_in_region_of_ethernet:
                self._handle_allocating_left_over_sdram(
                    bandwidth_resource, ethernet_connected_chip_x,
                    ethernet_connected_chip_y, chip, placements,
                    graph_mapper, partitionable_graph)

    @staticmethod
    def _handle_allocating_left_over_sdram(
            bandwidth_resource, ethernet_connected_chip_x,
            ethernet_connected_chip_y, chip, placements, graph_mapper,
            partitionable_graph):
        """

        :param bandwidth_resource:
        :param ethernet_connected_chip_x:
        :param ethernet_connected_chip_y:
        :param chip:
        :param placements:
        :param graph_mapper:
        :param partitionable_graph:
        :return:
        """

        chip_placements = placements.get_placements_on_chip(chip.x, chip.y)

        # search each placement to see if it can be allocated to the bandwidth
        for placement in chip_placements:
            vertex_slice = graph_mapper.get_subvertex_slice(placement.subvertex)
            vertex = graph_mapper.get_vertex_from_subvertex(placement.subvertex)
            if (isinstance(placement.subvertex, AbstractReceiveBuffersToHost)
                    and (not isinstance(
                        placement.subvertex,
                        ReverseIPTagMulticastSourcePartitionedVertex))):
                individual_machine_time_step_sdram_usage = \
                    vertex.get_runtime_sdram_usage_for_atoms(
                        vertex_slice, partitionable_graph, 1)

                # if the individual bandwidth is doable, remove it from the
                # bandwidth and continue, otherwise turn off its buffered
                #  capability
                if (individual_machine_time_step_sdram_usage <
                        bandwidth_resource[(ethernet_connected_chip_x,
                                            ethernet_connected_chip_y)]):
                    bandwidth_resource[(ethernet_connected_chip_x,
                                        ethernet_connected_chip_y)] -= \
                        individual_machine_time_step_sdram_usage

    @staticmethod
    def _update_ethernet_bandwidth_off_injectors(
            bandwidth_resource, placements, machine, partitioned_graph):

        # check if buffered out has to be given over to injectors
        for vertex in partitioned_graph.subvertices:
            if (isinstance(
                    vertex, ReverseIPTagMulticastSourcePartitionedVertex) and
                    vertex.buffering_output):
                placement = placements.get_placement_of_subvertex(vertex)
                chip = machine.get_chip_at(placement.x, placement.y)

                # remove all bandwidth from that local ethernet (as we
                # cant predict how much bandwidth is needed there)
                bandwidth_resource[(chip.nearest_ethernet_x,
                                    chip.nearest_ethernet_y)] = 0

    @staticmethod
    def _deduce_ethernet_connected_chips_bandwidth_resource(
            machine_time_step, time_scale_factor, machine):
        """

        :param machine_time_step:
        :param time_scale_factor:
        :param machine:
        :return:
        """

        # storage for each connected chip bandwidth left over
        resources = dict()

        # deduce how much bandwidth buffered out has to play with
        bandwidth_per_machine_time_step_per_ethernet_connected_chip = \
            (machine_time_step * time_scale_factor) * \
            machine.MAX_BANDWIDTH_PER_ETHERNET_CONNECTED_CHIP

        # create initial supply
        for chip in machine.ethernet_connected_chips:
            resources[(chip.x, chip.y)] = \
                bandwidth_per_machine_time_step_per_ethernet_connected_chip

        return resources

    def _setup_pacman_executor_inputs(
            self, wait_on_confirmation, partitionable_graph,
            send_start_notification, notification_interface, app_id, txrx,
            time_scale_factor, loaded_reverse_iptags_token, loaded_iptags_token,
            loaded_routing_tables_token, no_sync_changes,
            extra_inputs, extra_xmls,
            algorithm_for_dsg_generation, algorithm_for_dse_execution, tags,
            reports_states, app_data_folder, verify, routing_infos,
            placements, graph_mapper, partitioned_graph, machine,
            has_ran_before, has_reset_before, application_graph_changed,
            time_theshold):
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
        :param time_theshold:
        :return:
        """

        inputs = list()
        outputs = list()
        xmls = self.sort_out_xmls(extra_xmls)
        first_algorithms = list()
        optimal_algorithms = list()
        multi_iteration_algorithms = list()

        # standard algorithms needed for multi-runs before updater
        # (expected order here for debug purposes)
        first_algorithms.append("FrontEndCommonMachineTimeStepUpdater")
        if ((not has_ran_before and not has_reset_before) or
                application_graph_changed):
            # needs a dsg rebuild
            first_algorithms.append(algorithm_for_dsg_generation)
            first_algorithms.append(algorithm_for_dse_execution)
            first_algorithms.append("FrontEndCommonRuntimeUpdater")
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
        inputs.append({
            'type': "TimeTheshold",
            'value': time_theshold})

        return inputs, first_algorithms, optimal_algorithms, outputs, xmls

    @staticmethod
    def sort_out_xmls(extra_xmls):
        """

        :param extra_xmls:
        :return:
        """

        xmls = list()
        # add the extra xmls
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

            # if its the first iteration, do all the boiler plate of dsg, dse,
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
