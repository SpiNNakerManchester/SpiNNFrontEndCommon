# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Miscellaneous constants used in energy consumption calculations
"""

#: given from Indar's measurements
MILLIWATTS_PER_FPGA = 0.000584635

#: stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
#: Massively-Parallel Neural Network Simulation)
JOULES_PER_SPIKE = 0.000000000800

#: stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
#: Massively-Parallel Neural Network Simulation)
MILLIWATTS_PER_IDLE_CHIP = 0.000360

#: stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
#: Massively-Parallel Neural Network Simulation)
MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD = 0.001 - MILLIWATTS_PER_IDLE_CHIP

#: measured from the real power meter and timing between
#: the photos for a days powered off
MILLIWATTS_FOR_FRAME_IDLE_COST = 0.117

#: measured from the loading of the column and extrapolated
MILLIWATTS_PER_FRAME_ACTIVE_COST = 0.154163558

#: measured from the real power meter and timing between the photos
#: for a day powered off
MILLIWATTS_FOR_BOXED_48_CHIP_FRAME_IDLE_COST = 0.0045833333

# TODO needs filling in
MILLIWATTS_PER_UNBOXED_48_CHIP_FRAME_IDLE_COST = 0.01666667

# TODO verify this is correct when doing multiboard comms
#: Number of monitors active during communications
N_MONITORS_ACTIVE_DURING_COMMS = 2
