from pacman.operations.pacman_algorithm_executor import PACMANAlgorithmExecutor
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
    FrontEndCommonAutoPauseAndResumer: system that automaticlaly allocate
    bandwith resoruces and deduces what pause and resume functions are needed,
    and executes them accordingly
    """

    def __call__(
            self, partitioned_graph, runtime, wait_on_confirmation,
            send_start_notification, machine, notification_interface, app_id,
            txrx, time_scale_factor, loaded_reverse_iptags_token,
            loaded_iptags_token, loaded_routing_tables_token, graph_mapper,
            no_sync_changes, partitionable_graph, app_data_folder, verify,
            algorthums_to_run_between_runs, extra_inputs, extra_xmls,
            algorithum_for_dsg_generation, algorithum_for_dse_execution,
            machine_time_step, placements, tags, reports_states, routing_infos,
            has_ran_before, has_reset_before, application_graph_changed):

        steps = self._deduce_number_of_interations(
            partitioned_graph, runtime, time_scale_factor,
            machine, machine_time_step, placements, graph_mapper,
            partitionable_graph)

        if len(steps) != 1:
            logger.warn(
                "The simualtion required more SDRAM for recording purposes"
                " than what was avilable. Therefore the system deduced that"
                " it needs to run the simulation in {} chunks, where the "
                "chunks of time consists of {}. If this is not suitable for "
                "your usage, please turn off use_auto_pause_and_resume in "
                " your config file. Thank you")

        inputs, first_algorthims, optional_algorithms, multi_run_algorithms, \
            outputs, xmls = self._setup_pacman_executor_inputs(
                wait_on_confirmation, partitionable_graph,
                send_start_notification, notification_interface, app_id, txrx,
                time_scale_factor, loaded_reverse_iptags_token,
                loaded_iptags_token, loaded_routing_tables_token,
                no_sync_changes, algorthums_to_run_between_runs, extra_inputs,
                extra_xmls, algorithum_for_dsg_generation,
                algorithum_for_dse_execution, tags, reports_states,
                app_data_folder, verify, routing_infos, placements,
                graph_mapper, partitioned_graph, machine, has_ran_before,
                has_reset_before, application_graph_changed)

        no_sync_changes, executable_targets, dsg_targets, buffer_manager, \
            processor_to_app_data_base_address, \
            placement_to_application_data_files = \
            self._execute_pacman_system_number_of_iterations(
                steps, inputs, first_algorthims, optional_algorithms,
                multi_run_algorithms, outputs, xmls)

        return {
            'RanToken': True, "no_sync_changes": no_sync_changes,
            'executable_targets': executable_targets,
            'dsg_targets': dsg_targets, "buffer_manager": buffer_manager,
            'processor_to_app_data_base_address':
            processor_to_app_data_base_address,
            'placement_to_app_data_files':
            placement_to_application_data_files,
            "LoadedApplicationDataToken": True, "LoadBinariesToken": True,
            }

    def _deduce_number_of_interations(
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

        # build resoruce tracker for sdram usage
        resource_tracker = ResourceTracker(machine)

        # allocate static sdram usage to the resource tracker, leaving us
        # with just the sdram avilable for runtime usage
        for vertex in partitioned_graph.subvertices:
            resource_tracker.allocate_constrained_resources(
                vertex.resources_required, vertex.constraints)

        # update all ethenet resoruces for
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
            self._discover_min_time_steps_with_sdram_avilable(
                machine, placements, resource_tracker, graph_mapper,
                partitionable_graph)

        # calculate the steps array
        total_no_machine_time_steps = \
            (runtime / time_scale_factor) * (machine_time_step / 1000)
        number_of_full_iterations = \
            int(math.floor(
                total_no_machine_time_steps / min_machine_time_steps))
        left_over_time_steps = \
            int(total_no_machine_time_steps - (number_of_full_iterations *
                                               min_machine_time_steps))

        steps = list()
        for _ in range(0, number_of_full_iterations):
            steps.append(min_machine_time_steps)
        steps.append(left_over_time_steps)
        return steps

    def _discover_min_time_steps_with_sdram_avilable(
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
            chip_placments = placements.get_placements_on_chip(chip.x, chip.y)
            none_buffered_placements = list()
            for chip_placment in chip_placments:
                if self._check_for_none_buffered_functionality(chip_placment):
                    none_buffered_placements.append(chip_placment)

            sdram_left_over = \
                resource_tracker.sdram_avilable_on_chip(chip.x, chip.y)

            this_chips_min_machine_time_steps = \
                self._caculate_min_machine_time_step_for_bunch_of_placements(
                    none_buffered_placements, sdram_left_over, graph_mapper,
                    partitionable_graph)

            if this_chips_min_machine_time_steps < min_machine_time_steps:
                min_machine_time_steps = this_chips_min_machine_time_steps

        return min_machine_time_steps

    @staticmethod
    def _check_for_none_buffered_functionality(chip_placment):

        # get params
        is_r_i_m_c_s = isinstance(
            chip_placment.subvertex,
            ReverseIPTagMulticastSourcePartitionedVertex)
        is_sending_buffers_to_host = isinstance(
            chip_placment.subvertex, AbstractReceiveBuffersToHost)
        is_recording_stuff = isinstance(
            chip_placment.subvertex, AbstractRecordableInterface)

        # check if buffered out is turned on
        if not is_sending_buffers_to_host:
            buffered_out_turned_on = False
        else:
            buffered_out_turned_on = chip_placment.subvertex.buffering_output

        # do check
        if (not is_r_i_m_c_s and is_recording_stuff and
                (not is_sending_buffers_to_host) or
                (is_sending_buffers_to_host and not buffered_out_turned_on)):
            return True
        else:
            return False

    # overloadable method for optimisations on chip sdram distrubtion
    @staticmethod
    def _caculate_min_machine_time_step_for_bunch_of_placements(
            placements, sdram_left_over, graph_mapper, partitionable_graph):
        """

        :param placements:
        :param sdram_left_over:
        :param graph_mapper:
        :param partitionable_graph:
        :return:
        """
        # assuming shared equally, maybe optimsations for unbalanced usage
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
                        "Havent been programmed to handle models which change "
                        "their requriements of sdram within a runtime. Please "
                        "fix and try again")

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

        # search each placmeent to see if it can be allocated to the bandwidth
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
                # bandwidth and continue, toherwise turn off its buffered
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

        # storage for each connected chip bandewidth left over
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
            algorthums_to_run_between_runs, extra_inputs, extra_xmls,
            algorithum_for_dsg_generation, algorithum_for_dse_execution, tags,
            reports_states, app_data_folder, verify, routing_infos,
            placements, graph_mapper, partitioned_graph, machine,
            has_ran_before, has_reset_before, application_graph_changed):
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
        :param algorthums_to_run_between_runs:
        :param extra_inputs:
        :param extra_xmls:
        :param algorithum_for_dsg_generation:
        :param algorithum_for_dse_execution:
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
        optiomal_algorithms = list()
        multi_iteration_algorithms = list()

        # standard algorithms needed for multi-runs before updator
        # (expected order here for debug purposes)
        first_algorithms.append("FrontEndCommonMachineTimeStepUpdator")
        if ((not has_ran_before and not has_reset_before) or
                application_graph_changed):
            # needs a dsg rebuild
            first_algorithms.append(algorithum_for_dsg_generation)
            first_algorithms.append(algorithum_for_dse_execution)
            optiomal_algorithms.append("FrontEndCommonApplicationDataLoader")
            first_algorithms.append("FrontEndCommomLoadExecutableImages")
            first_algorithms.append("FrontEndCommonBufferManagerCreater")

        # has had a reset, but no need for dsg
        if not application_graph_changed and has_reset_before:
            first_algorithms.append("FrontEndCommonBufferManagerCreater")

        multi_iteration_algorithms.append("FrontEndCommonApplicationRunner")
        multi_iteration_algorithms.extend(algorthums_to_run_between_runs)
        multi_iteration_algorithms.append("FrontEndCommonRuntimeUpdater")

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

        return inputs, first_algorithms, optiomal_algorithms, \
            multi_iteration_algorithms, outputs, xmls

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
            multi_algorithms, outputs, xmls):
        """

        :param inputs:
        :param first_algorithms:
        :param outputs:
        :param optimal_algorithms:
        :param xmls:
        :param multi_algorithms
        :return:
        """
        pacman_executor = None
        for iteration in range(0, len(steps)):
            # during each iteration, you need to run:
            # application runner, no_machine_time_steps_updater,
            # EXTRA_ALOGIRTHMS, runtime_updater
            self._update_inputs(pacman_executor, inputs, steps, iteration)

            # if its the first iteration, do all the boiler plate of dsg, dse,
            # app data load, executable load, etc
            if iteration == 0:
                all_algorithms = first_algorithms + multi_algorithms
                pacman_executor = PACMANAlgorithmExecutor(
                    algorithms=all_algorithms, inputs=inputs, xml_paths=xmls,
                    required_outputs=outputs,
                    optional_algorithms=optimal_algorithms)
            else:
                pacman_executor = PACMANAlgorithmExecutor(
                    algorithms=multi_algorithms, inputs=inputs, xml_paths=xmls,
                    required_outputs=outputs,
                    optional_algorithms=optimal_algorithms)

            pacman_executor.execute_mapping()

        return pacman_executor.get_item("NoSyncChanges"), \
            pacman_executor.get_item("ExecutableTargets"), \
            pacman_executor.get_item("DataSpecificationTargets"), \
            pacman_executor.get_item("BufferManager"), \
            pacman_executor.get_item("ProcessorToAppDataBaseAddress"), \
            pacman_executor.get_item("PlacementToAppDataFilePaths")

    def _update_inputs(self, pacman_executor, inputs, steps, iteration):
        """

        :param pacman_executor:
        :param inputs:
        :param steps:
        :param iteration:
        :return:
        """
        if pacman_executor is not None:
            no_sync_changes = pacman_executor.get_item("NoSyncChanges")
            parameter_index = \
                self._locate_index_of_input(inputs, 'NoSyncChanges')
            inputs[parameter_index] = {
                'type': 'NoSyncChanges',
                'value': no_sync_changes}
            parameter_index = self._locate_index_of_input(inputs, 'Steps')
            inputs[parameter_index] = {
                'type': 'Steps',
                'value': steps}
            parameter_index = self._locate_index_of_input(inputs, 'Iteration')
            inputs[parameter_index] = {
                'type': 'Iteration',
                'value': iteration}
            parameter_index = self._locate_index_of_input(inputs, 'RunTime')
            inputs[parameter_index] = {
                'type': 'RunTime',
                'value': steps[iteration]}
        else:
            inputs.append({
                'type': 'RunTime',
                'value': steps[iteration]})
            inputs.append({
                'type': 'Steps',
                'value': steps})
            inputs.append({
                'type': 'Iteration',
                'value': iteration})

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
        return index


# TODO There must be a way to remove this requirement, but not sure how yet.
class FrontEndCommonMachineTimeStepUpdator(object):

    def __call__(self, iteration, steps, partitionable_graph):

        # deduce the new runtime position
        set_runtime = 0
        for past_step in range(0, iteration + 1):
            set_runtime += steps[past_step]

        # update the partitionable vertices
        for vertex in partitionable_graph.vertices:
            vertex.set_no_machine_time_steps(set_runtime)

        return {"runtime_in_machine_time_steps": set_runtime}
