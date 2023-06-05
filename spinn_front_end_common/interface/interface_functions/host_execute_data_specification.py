# Copyright (c) 2015 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import numpy
from spinn_utilities.config_holder import get_config_bool
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import (
    APPDATA_MAGIC_NUM, APP_PTR_TABLE_BYTE_SIZE, BYTES_PER_WORD,
    CORE_DATA_SDRAM_BASE_TAG, DSE_VERSION, MAX_MEM_REGIONS, TABLE_TYPE)
from spinn_front_end_common.utilities.exceptions import DataSpecException
from spinn_front_end_common.utilities.helpful_functions import (
    write_address_to_user0)
from spinn_front_end_common.utilities.emergency_recovery import (
    emergency_recover_states_from_failure)

logger = FormatAdapter(logging.getLogger(__name__))


def execute_system_data_specs():
    """
    Execute the data specs for all system targets.
    """
    specifier = _HostExecuteDataSpecification()
    return specifier.load_data_specs(True, False)


def execute_application_data_specs():
    """
    Execute the data specs for all non-system targets.
    """
    specifier = _HostExecuteDataSpecification()
    uses_advanced_monitors = get_config_bool(
        "Machine", "enable_advanced_monitor_support")
    # Allow config to override
    if get_config_bool(
            "Machine", "disable_advanced_monitor_usage_for_data_in"):
        uses_advanced_monitors = False
    try:
        specifier.load_data_specs(False, uses_advanced_monitors)
    except:  # noqa: E722
        if uses_advanced_monitors:
            emergency_recover_states_from_failure()
        raise


class _HostExecuteDataSpecification(object):
    """
    Executes the host based data specification.
    """

    __slots__ = []

    first = True

    def __set_router_timeouts(self):
        for receiver in FecDataView.iterate_gathers():
            receiver.load_system_routing_tables()
            receiver.set_cores_for_data_streaming()

    def __reset_router_timeouts(self):
        # reset router timeouts
        for receiver in FecDataView.iterate_gathers():
            receiver.unset_cores_for_data_streaming()
            # reset router tables
            receiver.load_application_routing_tables()

    # pylint: disable=unused-private-member
    def __java_app(self, use_monitors):
        """
        :param bool use_monitors:
        """
        # create a progress bar for end users
        progress = ProgressBar(
            2, "Executing data specifications and loading data for "
            "application vertices using Java")

        java_caller = FecDataView.get_java_caller()
        if use_monitors:
            # Method also called with just recording params
            java_caller.set_placements(FecDataView.iterate_placemements())
        progress.update()

        java_caller.execute_app_data_specification(use_monitors)
        progress.end()

    def load_data_specs(self, is_system, uses_advanced_monitors):
        """
        Execute the data specs for all system targets.
        """
        try:
            if FecDataView.has_java_caller():
                logger.warning("Java not being used for DS loading")
            #    if is_system:
            #        return self.__java_sys()
            #    else:
            #        return self.__java_app(uses_advanced_monitors)
            # else:
            return self.__python_load(is_system, uses_advanced_monitors)
        except:  # noqa: E722
            if uses_advanced_monitors:
                emergency_recover_states_from_failure()
            raise

    # pylint: disable=unused-private-member
    def __java_sys(self):
        """
        Does the Data Specification Execution and loading using Java.
        """
        # create a progress bar for end users
        progress = ProgressBar(
            1, "Executing data specifications and loading data for system "
            "vertices using Java")
        FecDataView.get_java_caller().execute_system_data_specification()
        progress.end()

    def __python_load(self, is_system, uses_advanced_monitors):
        """
        Does the Data Specification Execution and loading using Python.
        """
        if uses_advanced_monitors:
            self.__set_router_timeouts()

        # create a progress bar for end users
        dsg_targets = FecDataView.get_dsg_targets()

        # allocate and set user 0 before loading data

        transceiver = FecDataView.get_transceiver()
        writer = transceiver.write_memory
        core_infos = dsg_targets.get_core_infos(is_system)
        if is_system:
            type_str = "system"
        else:
            type_str = "application"
        progress = ProgressBar(
            len(core_infos) * 2,
            "Executing data specifications and loading data for "
            f"{type_str} vertices")

        for x, y, p, _, _ in progress.over(
                core_infos, finish_at_end=False):
            total_size = dsg_targets.get_total_regions_size(x, y, p)
            malloc_size = total_size + APP_PTR_TABLE_BYTE_SIZE
            start_address = self.__malloc_region_storage(x, y, p, malloc_size)
            expected_size = dsg_targets.set_start_address(
                x, y, p, start_address)
            if (malloc_size != expected_size):
                raise DataSpecException(
                    f"For {x=}{y=}{p=} {malloc_size=} != {expected_size=}")

        for x, y, p, eth_x, eth_y in progress.over(core_infos):
            if uses_advanced_monitors:
                gatherer = FecDataView.get_gatherer_by_xy(eth_x, eth_y)
                writer = gatherer.send_data_into_spinnaker
            written = self.__python_load_core(dsg_targets, x, y, p, writer)
            to_write = dsg_targets.get_memory_to_write(x, y, p)
            if (malloc_size != expected_size):
                raise DataSpecException(
                    f"For {x=}{y=}{p=} {written=} != {to_write=}")

        if uses_advanced_monitors:
            self.__reset_router_timeouts()

    def __python_load_core(self, dsg_targets, x, y, p, writer):
        written = 0
        pointer_table = numpy.zeros(
            MAX_MEM_REGIONS, dtype=TABLE_TYPE)
        for region_num, pointer, content in \
                dsg_targets.get_region_pointers_and_content(x, y, p):
            pointer_table[region_num]["pointer"] = pointer

            if content is None:
                continue

            writer(x, y, pointer, content)
            n_bytes = len(content)
            written += n_bytes
            if n_bytes % BYTES_PER_WORD != 0:
                n_bytes += BYTES_PER_WORD - n_bytes % BYTES_PER_WORD
            pointer_table[region_num]["n_words"] = n_bytes / BYTES_PER_WORD
            n_data = numpy.array(content, dtype="uint8")
            pointer_table[region_num]["checksum"] = \
                int(numpy.sum(n_data.view("uint32"))) & 0xFFFFFFFF

        try:
            for region_num, pointer in dsg_targets.get_reference_pointers(
                    x, y, p):
                pointer_table[region_num]["pointer"] = pointer
        except TypeError:
            if pointer is None:
                raise DataSpecException(
                    f"{x=} {y=} {p=} {region_num=} has a unsatisfied pointer")
            raise

        base_address = dsg_targets.get_start_address(x, y, p)
        header = numpy.array([APPDATA_MAGIC_NUM, DSE_VERSION], dtype="<u4")

        to_write = numpy.concatenate(
            (header, pointer_table.view("uint32"))).tobytes()
        writer(x, y, base_address, to_write)
        written += len(to_write)
        return written

    def __malloc_region_storage(self, x, y, p, size):
        """
        Allocates the storage for all DSG regions on the core and tells
        the core and our caller where that storage is.

        :param int x:
        :param int y:
        :param int p:
        :param int size:
            The total size of all storage for regions on that core, including
            for the header metadata.
        :return: address of region header table (not yet filled)
        :rtype: int
        """

        # allocate memory where the app data is going to be written; this
        # raises an exception in case there is not enough SDRAM to allocate
        start_address = FecDataView.get_transceiver().malloc_sdram(
            x, y, size, FecDataView.get_app_id(),
            tag=CORE_DATA_SDRAM_BASE_TAG + p)

        # set user 0 register appropriately to the application data
        write_address_to_user0(x, y, p, start_address)

        return start_address
