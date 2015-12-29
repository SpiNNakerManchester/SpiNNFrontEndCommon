from pacman.operations.pacman_algorithm_executor import PACMANAlgorithmExecutor

from spinn_front_end_common.interface import interface_functions

import os

class FrontEndCommonAutoPauseAndResumer(object):

    def __call__(
            self, partitioned_graph, no_machine_time_steps, buffer_manager,
            wait_on_confirmation, send_start_notification, machine,
            notification_interface, executable_targets, app_id, txrx,
            time_scale_factor, loaded_reverse_iptags_token, loaded_iptags_token,
            loaded_routing_tables_token, loaded_binaries_token,
            loaded_application_data_token, no_sync_changes, partitionable_graph,
            algorthums_to_run_between_runs, extra_inputs, extra_xmls):

        steps = self._deduce_number_of_interations(
            partitioned_graph, no_machine_time_steps, machine)

        inputs, algorthims, outputs, xmls = self._setup_pacman_executor_inputs(
            buffer_manager, wait_on_confirmation, partitionable_graph,
            send_start_notification, notification_interface,
            executable_targets, app_id, txrx, time_scale_factor,
            loaded_reverse_iptags_token, loaded_iptags_token,
            loaded_routing_tables_token, loaded_binaries_token,
            loaded_application_data_token, no_sync_changes,
            algorthums_to_run_between_runs, extra_inputs, extra_xmls)

        no_sync_changes = self._execute_pacman_system_number_of_iterations(
            steps, inputs, algorthims, outputs, xmls)

        return {'RanToken': True, "no_sync_changes": no_sync_changes}

    def _setup_pacman_executor_inputs(
            self, buffer_manager, wait_on_confirmation, partitionable_graph,
            send_start_notification, notification_interface,
            executable_targets, app_id, txrx, time_scale_factor,
            loaded_reverse_iptags_token, loaded_iptags_token,
            loaded_routing_tables_token, loaded_binaries_token,
            loaded_application_data_token, no_sync_changes,
            algorthums_to_run_between_runs, extra_inputs, extra_xmls):

        inputs = list()
        outputs = list()
        xmls = self.sort_out_xmls(extra_xmls)
        algorithms = list()

        # standard algorithms needed for multi-runs before updator
        algorithms.append("FrontEndCommonApplicationRunner")
        algorithms.append("FrontEndCommonNMachineTimeStepUpdator")
        algorithms.extend(algorthums_to_run_between_runs)
        algorithms.append("FrontEndCommonRuntimeUpdater")

        # handle outputs
        # TODO is this all i need here????
        outputs.append("RanToken")

        # handle inputs
        inputs.extend(extra_inputs)
        inputs.append({'type': "BufferManager", 'value': buffer_manager})
        inputs.append({'type': "DatabaseWaitOnConfirmationFlag",
                       'value': wait_on_confirmation})
        inputs.append({'type': "MemoryPartitionableGraph",
                       'value': partitionable_graph})
        inputs.append({'type': "SendStartNotifications",
                       'value': send_start_notification})
        inputs.append({'type': "NotificationInterface",
                       'value': notification_interface})
        inputs.append({'type': "ExecutableTargets",
                       'value': executable_targets})
        inputs.append({'type': "APPID", 'value': app_id})
        inputs.append({'type': "MemoryTransciever", 'value': txrx})
        inputs.append({'type': "TimeScaleFactor", 'value': time_scale_factor})
        inputs.append({'type': "LoadedReverseIPTagsToken",
                       'value': loaded_reverse_iptags_token})
        inputs.append({'type': "LoadedIPTagsToken",
                       'value': loaded_iptags_token})
        inputs.append({'type': "LoadedRoutingTablesToken",
                       'value': loaded_routing_tables_token})
        inputs.append({'type': "LoadBinariesToken",
                       'value': loaded_binaries_token})
        inputs.append({'type': "LoadedApplicationDataToken",
                       'value': loaded_application_data_token})
        inputs.append({'type': "NoSyncChanges", 'value': no_sync_changes})

        return inputs, algorithms, outputs, xmls

    @staticmethod
    def sort_out_xmls(extra_xmls):
        xmls = list()
        # add the extra xmls
        xmls.extend(extra_xmls)

        #check that the front end common xml has been put in, if not, put in
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
            self, steps, inputs, algorthims, outputs, xmls):
        """

        :param inputs:
        :param algorthims:
        :param outputs:
        :param xmls:
        :return:
        """
        pacman_executor = None
        for iteration in range(0, len(steps)):
            # during each iteration, you need to run:
            # application runner, no_machine_time_steps_updater,
            # EXTRA_ALOGIRTHMS, runtime_updater
            self._update_inputs(pacman_executor, inputs, steps, iteration)

            pacman_executor = PACMANAlgorithmExecutor(
                algorithms=algorthims, inputs=inputs, xml_paths=xmls,
                required_outputs=outputs)
            pacman_executor.execute_mapping()

        return pacman_executor.get_item("NoSyncChanges")

    def _update_inputs(self, pacman_executor, inputs, steps, iteration):
        """

        :param pacman_executor:
        :param inputs:
        :param steps:
        :param iteration:
        :return:
        """
        no_sync_changes = pacman_executor.get_item("NoSyncChanges")
        parameter_index = self._locate_index_of_input(inputs, 'NoSyncChanges')
        inputs[parameter_index] = {'type': 'NoSyncChanges',
                                   'value': no_sync_changes}
        parameter_index = self._locate_index_of_input(inputs, 'Runtime')
        inputs[parameter_index] = {'type': 'Runtime',
                                   'value': steps[iteration]}
        parameter_index = self._locate_index_of_input(inputs, 'Steps')
        inputs[parameter_index] = {'type': 'Steps', 'value': steps}
        parameter_index = self._locate_index_of_input(inputs, 'Iteration')
        inputs[parameter_index] = {'type': 'Iteration', 'value': iteration}

    @staticmethod
    def _locate_index_of_input(inputs, type_name):
        index = 0
        found = False
        while not found and index < len(inputs):
            current_input = inputs[index]
            if current_input['type'] == type_name:
                found = True
            else:
                index += 1
        return index


class FrontEndCommonNMachineTimeStepUpdator(object):

    def __call__(self, iteration, steps, partitionable_graph):
        for vertex in partitionable_graph.vertices:
            vertex.set_no_machine_time_steps(steps[iteration])
