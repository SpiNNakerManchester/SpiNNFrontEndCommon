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
-- A table assigning ids to source names
CREATE TABLE IF NOT EXISTS source(
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name STRING UNIQUE NOT NULL,
    source_short_name STRING NOT NULL,
    x INTEGER,
    y INTEGER,
    p INTEGER);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table assigning ids to description names
CREATE TABLE IF NOT EXISTS description(
    description_id INTEGER PRIMARY KEY AUTOINCREMENT,
    description_name STRING UNIQUE NOT NULL);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values
CREATE TABLE IF NOT EXISTS provenance(
    provenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    description_id INTEGER NOT NULL,
    the_value INTEGER NOT NULL);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for versions
CREATE TABLE IF NOT EXISTS version_provenance(
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    description STRING NOT NULL,
    the_value STRING NOT NULL);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for versions
CREATE TABLE IF NOT EXISTS timer_provenance(
    timer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category STRING NOT NULL,
    algorithm STRING NOT NULL,
    the_value INTEGER NOT NULL);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for uncategorised general provenance
CREATE TABLE IF NOT EXISTS other_provenance(
    other_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category STRING NOT NULL,
    description STRING NOT NULL,
    the_value INTEGER NOT NULL);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for monitors
CREATE TABLE IF NOT EXISTS monitor_provenance(
    chip_id INTEGER PRIMARY KEY AUTOINCREMENT,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    description STRING NOT NULL,
    the_value INTEGER NOT NULL);

-- Compute some basic statistics per monitor over the monitorr provenance
CREATE VIEW IF NOT EXISTS monitor_stats_view AS
    SELECT
		x, y, description,
        min(the_value) AS min,
        max(the_value) AS max,
        avg(the_value) AS avg,
        sum(the_value) AS total,
        count(the_value) AS count
    FROM monitor_provenance
    GROUP BY x, y, description;

-- Compute some basic statistics for all monitors over the monitor provenance
CREATE VIEW IF NOT EXISTS monitor_summary_view AS
    SELECT
		description,
        min(the_value) AS min,
        max(the_value) AS max,
        avg(the_value) AS avg,
        sum(the_value) AS total,
        count(the_value) AS count
    FROM monitor_provenance
    GROUP BY description;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for routers
CREATE TABLE IF NOT EXISTS router_provenance(
    chip_id INTEGER PRIMARY KEY AUTOINCREMENT,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    description STRING NOT NULL,
    the_value INTEGER NOT NULL,
    expected INTEGER NOT NULL);

-- Compute some basic statistics per router over the router provenance
CREATE VIEW IF NOT EXISTS router_stats_view AS
    SELECT
		x, y, description,
        min(the_value) AS min,
        max(the_value) AS max,
        avg(the_value) AS avg,
        sum(the_value) AS total,
        count(the_value) AS count,
        avg(expected) as expected
    FROM router_provenance
    GROUP BY x, y, description;

-- Compute some basic statistics for all router over the router provenance
CREATE VIEW IF NOT EXISTS router_summary_view AS
    SELECT
		description,
        min(the_value) AS min,
        max(the_value) AS max,
        avg(the_value) AS avg,
        sum(the_value) AS total,
        count(the_value) AS count,
        avg(expected) as expected
    FROM router_provenance
    GROUP BY description;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for each core
CREATE TABLE IF NOT EXISTS core_provenance(
    core_id INTEGER PRIMARY KEY AUTOINCREMENT,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    p INTEGER NOT NULL,
    description STRING NOT NULL,
    the_value INTEGER NOT NULL);

-- A table holding the mapping from vertex name to core x, y, p
CREATE TABLE IF NOT EXISTS core_mapping(
    core_name STRING NOT NULL,
    x INTEGER,
    y INTEGER,
    p INTEGER);

-- Every core has a unique x,y,p location.
CREATE UNIQUE INDEX IF NOT EXISTS core_sanity ON core_mapping(
	x ASC, y ASC, p ASC);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- Compute some basic statistics per core over the provenance
CREATE VIEW IF NOT EXISTS core_stats_view AS
    SELECT
		core_name, x, y, p, description,
        min(the_value) AS min,
        max(the_value) AS max,
        avg(the_value) AS avg,
        sum(the_value) AS total,
        count(the_value) AS count
    FROM core_provenance_view
    GROUP BY core_name, x, y, p, description;

-- Compute some basic statistics for all cores over the core provenance
CREATE VIEW IF NOT EXISTS core_summary_view AS
    SELECT
		description,
        min(the_value) AS min,
        max(the_value) AS max,
        avg(the_value) AS avg,
        sum(the_value) AS total,
        count(the_value) AS count
    FROM core_provenance_view
    GROUP BY description;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the import reports
CREATE TABLE IF NOT EXISTS reports(
    message STRING NOT NULL);


-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- Glue the bits together to show the information that people think is here
CREATE VIEW IF NOT EXISTS provenance_view AS
    SELECT source_id, description_id, provenance_id,
    	source_short_name AS source_name, source_name AS source_full_name,
    	x, y, p, description_name, the_value
    FROM source NATURAL JOIN description NATURAL JOIN provenance;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- Show purely core level provenance, as most used
CREATE VIEW IF NOT EXISTS core_provenance_view AS
    SELECT core_id AS insertion_order,
    	core_name, x, y, p, description, the_value
    FROM core_provenance NATURAL JOIN core_mapping;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- Show purely edge level provenance, as most used
CREATE VIEW IF NOT EXISTS edge_provenance_view AS
    SELECT source_name, description_name, the_value
    FROM source NATURAL JOIN description NATURAL JOIN provenance
    WHERE source_short_name LIKE '%connector%';


