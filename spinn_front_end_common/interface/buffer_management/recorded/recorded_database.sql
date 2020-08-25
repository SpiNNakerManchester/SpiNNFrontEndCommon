-- Copyright (c) 2018-2019 The University of Manchester
--
-- This program is free software: you can redistribute it and/or modify
-- it under the terms of the GNU General Public License as published by
-- the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.
--
-- This program is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU General Public License for more details.
--
-- You should have received a copy of the GNU General Public License
-- along with this program.  If not, see <http://www.gnu.org/licenses/>.

-- https://www.sqlite.org/pragma.html#pragma_synchronous
PRAGMA main.synchronous = OFF;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
--  Table of source names and other infor which the user may have provided
CREATE TABLE IF NOT EXISTS sources(
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name STRING NOT NULL,
	description STRING,
    id_offset INTEGER);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
--  Table of variables names and other info which the user may have provided
CREATE TABLE IF NOT EXISTS variables(
    variable_id INTEGER PRIMARY KEY AUTOINCREMENT,
    variable_name STRING NOT NULL,
    source_id INTEGER,
	units STRING,
	min_key INTEGER,
	max_key INTEGER,
	key_step INTEGER NON NULL,
	data_type STRING,
	table_type STRING,
    UNIQUE(source_id, variable_name));

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
--  Table by variable of system generated info for each core
CREATE TABLE IF NOT EXISTS local_metadata(
	variable_id INTEGER NOT NULL,
	first_neuron_id INTEGER,
	raw_table STRING NOT NULL,
	best_source STRING,
	UNIQUE(variable_id, first_neuron_id));

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
--  Table by variable of system generated info for all cores
CREATE TABLE IF NOT EXISTS global_metadata(
	variable_id STRING NOT NULL,
	best_source STRING,
	min_key INTEGER NOT NULL,
	max_key INTEGER NOT NULL,
	UNIQUE(variable_id));
