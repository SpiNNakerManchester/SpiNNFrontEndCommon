# Copyright (c) 2026 The University of Manchester
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

from collections import defaultdict
from typing import Dict, Tuple, cast, Any
import numpy
import json

from spinn_utilities.config_holder import get_report_path
from spinn_machine.version.abstract_version import AbstractVersion
from spinnman.model.enums.executable_type import ExecutableType
from spinn_front_end_common.data.fec_data_view import FecDataView
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.interface.buffer_management\
    .storage_objects import BufferDatabase
from spinn_front_end_common.utility_models\
    .chip_power_monitor_machine_vertex import (
        RECORDING_CHANNEL, ChipPowerMonitorMachineVertex)


def write_sample_profile_report() -> None:
    """ Write a report of the profile data collected using the chip power
        monitor to measure active time.  The report is then, per core,
        the minimum, maximum and mean number of times the core was active when
        sampled.
    """

    report_path = get_report_path("path_sample_profile_report")
    version = FecDataView.get_machine_version()

    power_cores = get_power_cores()
    chip_activity = extract_core_activity(power_cores, version)
    timestep_us = FecDataView.get_simulation_time_step_us()

    json_report_data: Dict[str, Any] = {}
    json_report_data["timestep_us"] = timestep_us
    for (x, y), activity in chip_activity.items():
        p, active_cores = power_cores[(x, y)]
        vertex = cast(
            ChipPowerMonitorMachineVertex,
            FecDataView.get_placement_on_processor(x, y, p).vertex)
        min_active = numpy.min(activity, axis=0)
        max_active = numpy.max(activity, axis=0)
        mean_active = numpy.mean(activity, axis=0)
        sample_us = vertex.sampling_frequency
        n_samples = vertex.n_samples_per_recording
        min_percent = (min_active / n_samples) * 100
        max_percent = (max_active / n_samples) * 100
        mean_percent = (mean_active / n_samples) * 100

        json_report_chip: Dict[str, Any] = {}
        json_report_data[f"chip_{x}_{y}"] = json_report_chip
        json_report_chip["x"] = x
        json_report_chip["y"] = y
        json_report_chip["sample_frequency_us"] = sample_us
        json_report_chip["n_samples_per_recording"] = n_samples
        for v_id in active_cores:
            placement = FecDataView.get_placement_on_processor(
                x, y, v_id)
            if placement is None:
                continue
            core_vertex = placement.vertex
            p_id = FecDataView.get_physical_core_id((x, y), v_id)
            json_report_chip[f"core_{v_id}"] = {
                "vertex": core_vertex.app_vertex.__class__.__name__,
                "vertex_slice": str(core_vertex.vertex_slice),
                "vertex_label": core_vertex.label,
                "min_count_active": min_active[p_id],
                "max_count_active": max_active[p_id],
                "mean_count_active": mean_active[p_id],
                "min_percent_active": float(min_percent[p_id]),
                "max_percent_active": float(max_percent[p_id]),
                "mean_percent_active": float(mean_percent[p_id])
            }

    with open(report_path, "w", encoding="utf8") as report_file:
        json.dump(json_report_data, report_file, indent=4)


def get_power_cores() -> Dict[
        Tuple[int, int], Tuple[int, list[int]]]:
    """
    Get the power monitor cores, and the list of active cores

    :return: a dictionary mapping (x, y) coordinates to a tuple of:
          - the core ID of the power monitor core on that chip
          - the list of cores that were active on that chip
           (excluding the power monitor core)
    """
    power_cores: Dict[Tuple[int, int], int] = {}
    active_cores: Dict[Tuple[int, int], list[int]] = defaultdict(list)
    for pl in FecDataView.iterate_placemements():
        if not isinstance(pl.vertex, AbstractHasAssociatedBinary):
            continue
        vertex: AbstractHasAssociatedBinary = cast(
            AbstractHasAssociatedBinary, pl.vertex)
        if vertex.get_binary_start_type() != ExecutableType.SYSTEM:
            if isinstance(vertex, ChipPowerMonitorMachineVertex):
                power_cores[(pl.x, pl.y)] = pl.p
            else:
                active_cores[(pl.x, pl.y)].append(pl.p)

    return {xy: (power_cores[xy], active_cores[xy])
            for xy in power_cores if xy in active_cores}


def extract_core_activity(
        power_cores: Dict[Tuple[int, int], Tuple[int, list[int]]],
        version: AbstractVersion) -> Dict[Tuple[int, int], numpy.ndarray]:
    """ Extract the core activity data from the buffer database for each chip
        that has a power monitor core.

    :param power_cores: a dictionary mapping (x, y) coordinates to a tuple of:
            - the core ID of the power monitor core on that chip
            - the list of cores that were active on that chip
             (excluding the power monitor core)
    :param version: the machine version
    :return: a dictionary mapping (x, y) coordinates to a numpy array of shape
                (n_samples, n_cores) where n_samples is the number of samples
                recorded by the power monitor core, and n_cores is the number of
                cores on the chip.
                Each entry in the array is the count of times that core was
                active when sampled.
    """
    chip_activity: Dict[Tuple[int, int], numpy.ndarray] = {}
    with BufferDatabase() as buff_db:
        for (x, y) in power_cores:
            # Find the core that was used on this chip for power monitoring
            p, _active_cores = power_cores[(x, y)]
            # Get data from the power monitor core on this chip
            data, _missing = buff_db.get_recording(x, y, p, RECORDING_CHANNEL)
            results = numpy.frombuffer(data, dtype=numpy.uint32).reshape(
                -1, version.max_cores_per_chip + 1)
            # The first column is the time stamp of the recording,
            # the remaining columns are the counts of active / inactive at
            # each sample point
            activity = results[:, 1:].astype(numpy.float64)
            chip_activity[(x, y)] = activity
    return chip_activity
