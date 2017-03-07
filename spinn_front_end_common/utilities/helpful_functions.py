# dsg imports
from data_specification import utility_calls

# front end common imports
from spinn_front_end_common.interface import interface_functions
from spinn_front_end_common.utilities import report_functions as \
    front_end_common_report_functions
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities.utility_objs.executable_targets\
    import ExecutableTargets

# spinnman imports
from spinnman.model.cpu_state import CPUState
from spinn_machine.core_subsets import CoreSubsets
from spinn_machine.core_subset import CoreSubset

# general imports
import os
import logging
import struct
import time
from collections import OrderedDict

logger = logging.getLogger(__name__)
FINISHED_FILENAME = "finished"


def read_data(x, y, address, length, data_format, transceiver):
    """ Reads and converts a single data item from memory

    :param x: chip x
    :param y: chip y
    :param address: base address of the SDRAM chip to read
    :param length: length to read
    :param data_format: the format to read memory
    :param transceiver: the SpinnMan interface
    """

    # turn byte array into str for unpack to work
    data = buffer(transceiver.read_memory(x, y, address, length))
    result = struct.unpack_from(data_format, data)[0]
    return result


def locate_memory_region_for_placement(placement, region, transceiver):
    """ Get the address of a region for a placement

    :param region: the region to locate the base address of
    :type region: int
    :param placement: the placement object to get the region address of
    :type placement: pacman.model.placements.placement.Placement
    :param transceiver: the python interface to the spinnaker machine
    :type transceiver: spiNNMan.transciever.Transciever
    """
    regions_base_address = transceiver.get_cpu_information_from_core(
        placement.x, placement.y, placement.p).user[0]

    # Get the position of the region in the pointer table
    region_offset_in_pointer_table = \
        utility_calls.get_region_base_address_offset(
            regions_base_address, region)
    region_address = buffer(transceiver.read_memory(
        placement.x, placement.y, region_offset_in_pointer_table, 4))
    region_address_decoded = struct.unpack_from("<I", region_address)[0]
    return region_address_decoded


def get_front_end_common_pacman_xml_paths():
    """ Get the XML path for the front end common interface functions
    """
    return [
        os.path.join(
            os.path.dirname(interface_functions.__file__),
            "front_end_common_interface_functions.xml"),
        os.path.join(
            os.path.dirname(front_end_common_report_functions.__file__),
            "front_end_common_reports.xml")
    ]


def get_cores_in_state(all_core_subsets, states, txrx):
    """

    :param all_core_subsets:
    :param states:
    :param txrx:
    """
    core_infos = txrx.get_cpu_information(all_core_subsets)
    cores_in_state = OrderedDict()
    for core_info in core_infos:
        if hasattr(states, "__iter__"):
            if core_info.state in states:
                cores_in_state[
                    (core_info.x, core_info.y, core_info.p)] = core_info
        elif core_info.state == states:
            cores_in_state[
                (core_info.x, core_info.y, core_info.p)] = core_info

    return cores_in_state


def get_cores_not_in_state(all_core_subsets, states, txrx):
    """

    :param all_core_subsets:
    :param states:
    :param txrx:
    """
    core_infos = txrx.get_cpu_information(all_core_subsets)
    cores_not_in_state = OrderedDict()
    for core_info in core_infos:
        if hasattr(states, "__iter__"):
            if core_info.state not in states:
                cores_not_in_state[
                    (core_info.x, core_info.y, core_info.p)] = core_info
        elif core_info.state != states:
            cores_not_in_state[
                (core_info.x, core_info.y, core_info.p)] = core_info
    return cores_not_in_state


def get_core_status_string(core_infos):
    """ Get a string indicating the status of the given cores
    """
    break_down = "\n"
    for ((x, y, p), core_info) in core_infos.iteritems():
        if core_info.state == CPUState.RUN_TIME_EXCEPTION:
            break_down += "    {}:{}:{} in state {}:{}\n".format(
                x, y, p, core_info.state.name,
                core_info.run_time_error.name)
        else:
            break_down += "    {}:{}:{} in state {}\n".format(
                x, y, p, core_info.state.name)
    return break_down


def get_core_subsets(core_infos):
    """ Convert core information from get_cores_in_state to core_subset objects
    """
    core_subsets = CoreSubsets()
    for (x, y, p) in core_infos:
        core_subsets.add_processor(x, y, p)
    return core_subsets


def convert_string_info_chip_and_core_subsets(downed_chips, downed_cores):
    """ Translate the down cores and down chips string into a form that \
        spinnman can understand

    :param downed_cores: string representing down cores
    :type downed_cores: str or None
    :param downed_chips: string representing down chips
    :type downed_chips: str or None
    :return: a list of down cores and down chips in processor and \
            core subset format
    """
    ignored_chips = None
    ignored_cores = None
    if downed_chips is not None and downed_chips != "None":
        ignored_chips = CoreSubsets()
        for downed_chip in downed_chips.split(":"):
            x, y = downed_chip.split(",")
            ignored_chips.add_core_subset(CoreSubset(int(x), int(y),
                                                     []))
    if downed_cores is not None and downed_cores != "None":
        ignored_cores = CoreSubsets()
        for downed_core in downed_cores.split(":"):
            x, y, processor_id = downed_core.split(",")
            ignored_cores.add_processor(int(x), int(y),
                                        int(processor_id))
    return ignored_chips, ignored_cores


def translate_iobuf_extraction_elements(
        hard_coded_cores, hard_coded_model_binary, executable_targets,
        executable_finder):
    """

    :param hard_coded_cores: list of cores to read iobuf from
    :param hard_coded_model_binary: list of binary names to read iobuf from
    :param executable_targets: the targets of cores and executable binaries
    :param executable_finder: where to find binaries paths from binary names
    :return: core subsets for the cores to read iobuf from
    """
    # all the cores
    if hard_coded_cores == "ALL" and hard_coded_model_binary == "None":
        return executable_targets.all_core_subsets

    # some hard coded cores
    if hard_coded_cores != "None" and hard_coded_model_binary == "None":
        _, ignored_cores = convert_string_info_chip_and_core_subsets(
            None, hard_coded_cores)
        return ignored_cores

    # some binaries
    if hard_coded_cores == "None" and hard_coded_model_binary != "None":
        return _handle_model_binaries(
            hard_coded_model_binary, executable_targets, executable_finder)

    # nothing
    if hard_coded_cores == "None" and hard_coded_model_binary == "None":
        return CoreSubsets()

    # bit of both
    if hard_coded_cores != "None" and hard_coded_model_binary != "None":
        model_core_subsets = _handle_model_binaries(
            hard_coded_model_binary, executable_targets, executable_finder)
        _, hard_coded_core_core_subsets = \
            convert_string_info_chip_and_core_subsets(None, hard_coded_cores)
        for core_subset in hard_coded_core_core_subsets:
            model_core_subsets.add_core_subset(core_subset)
        return model_core_subsets

    # should never get here,
    raise exceptions.ConfigurationException("Something odd has happened")


def _handle_model_binaries(
        hard_coded_model_binary, executable_targets, executable_finder):
    """
    :param hard_coded_model_binary: list of binary names to read iobuf from
    :param executable_targets: the targets of cores and executable binaries
    :param executable_finder: where to find binaries paths from binary names
    :return: core subsets from binaries that need iobuf to be read from them
    """
    model_binaries = hard_coded_model_binary.split(",")
    cores = CoreSubsets()
    for model_binary in model_binaries:
        model_binary_path = \
            executable_finder.get_executable_path(model_binary)
        core_subsets = \
            executable_targets.get_cores_for_binary(model_binary_path)
        for core_subset in core_subsets:
            cores.add_core_subset(core_subset)
    return cores


def wait_for_cores_to_be_ready(executable_targets, app_id, txrx, sync_state):
    """

    :param executable_targets: the mapping between cores and binaries
    :param app_id: the app id that being used by the simulation
    :param txrx: the python interface to the spinnaker machine
    :param sync_state: The expected state once the applications are ready
    :rtype: None
    """

    total_processors = executable_targets.total_processors
    all_core_subsets = executable_targets.all_core_subsets

    # check that everything has gone though c main
    processor_c_main = txrx.get_core_state_count(app_id, CPUState.C_MAIN)
    while processor_c_main != 0:
        time.sleep(0.1)
        processor_c_main = txrx.get_core_state_count(
            app_id, CPUState.C_MAIN)

    # check that the right number of processors are in sync state
    processors_ready = txrx.get_core_state_count(
        app_id, sync_state)
    if processors_ready != total_processors:
        unsuccessful_cores = get_cores_not_in_state(
            all_core_subsets, sync_state, txrx)

        # last chance to slip out of error check
        if len(unsuccessful_cores) != 0:
            break_down = get_core_status_string(
                unsuccessful_cores)
            raise exceptions.ExecutableFailedToStartException(
                "Only {} processors out of {} have successfully reached "
                "{}:{}".format(
                    processors_ready, total_processors, sync_state.name,
                    break_down),
                get_core_subsets(unsuccessful_cores))


def get_executables_by_run_type(
        executable_targets, placements, graph_mapper, type_to_find):
    """ Get executables by the type of the vertices
    """

    # Divide executables by type
    matching_executables = ExecutableTargets()
    other_executables = ExecutableTargets()
    for binary in executable_targets.binaries:
        core_subsets = executable_targets.get_cores_for_binary(binary)
        for core_subset in core_subsets:
            for p in core_subset.processor_ids:
                vertex = placements.get_vertex_on_processor(
                    core_subset.x, core_subset.y, p)
                is_of_type = False
                if isinstance(vertex, type_to_find):
                    matching_executables.add_processor(
                        binary, core_subset.x, core_subset.y, p)
                    is_of_type = True
                elif graph_mapper is not None:
                    assoc_vertex = graph_mapper.get_application_vertex(vertex)
                    if isinstance(assoc_vertex, type_to_find):
                        matching_executables.add_processor(
                            binary, core_subset.x, core_subset.y, p)
                        is_of_type = True
                if not is_of_type:
                    other_executables.add_processor(
                        binary, core_subset.x, core_subset.y, p)
    return matching_executables, other_executables


def read_config(config, section, item):
    """ Get the string value of a config item, returning None if the value\
        is "None"
    """
    value = config.get(section, item)
    if value == "None":
        return None
    return value


def read_config_int(config, section, item):
    """ Get the integer value of a config item, returning None if the value\
        is "None"
    """
    value = read_config(config, section, item)
    if value is None:
        return value
    return int(value)


def read_config_boolean(config, section, item):
    """ Get the boolean value of a config item, returning None if the value\
        is "None"
    """
    value = read_config(config, section, item)
    if value is None:
        return value
    return bool(value)
