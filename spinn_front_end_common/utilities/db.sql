-- Copyright (c) 2018 The University of Manchester
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     https://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

-- https://www.sqlite.org/pragma.html#pragma_synchronous
PRAGMA main.synchronous = OFF;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing the cores.
CREATE TABLE IF NOT EXISTS core(
    core_id INTEGER PRIMARY KEY AUTOINCREMENT,
	x INTEGER NOT NULL,
	y INTEGER NOT NULL,
	processor INTEGER NOT NULL,
	core_name STRING);
-- Every processor has a unique ID
CREATE UNIQUE INDEX IF NOT EXISTS coreSanity ON core(
	x ASC, y ASC, processor ASC);


-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing recording regions.
CREATE TABLE IF NOT EXISTS region(
	region_id INTEGER PRIMARY KEY AUTOINCREMENT,
	core_id INTEGER NOT NULL
		REFERENCES core(core_id) ON DELETE RESTRICT,
	local_region_index INTEGER NOT NULL,
	address INTEGER,
	content BLOB NOT NULL DEFAULT '',
	content_len INTEGER DEFAULT 0,
	fetches INTEGER NOT NULL DEFAULT 0,
	append_time INTEGER);
-- Every recording region has a unique vertex and index
CREATE UNIQUE INDEX IF NOT EXISTS regionSanity ON region(
	core_id ASC, local_region_index ASC);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table containing the data which doesn't fit in the content column of the
-- region table; care must be taken with this to not exceed 1GB! We actually
-- store one per auto-pause-resume cycle as that is more efficient.
CREATE TABLE IF NOT EXISTS region_extra(
	extra_id INTEGER PRIMARY KEY ASC AUTOINCREMENT,
	region_id INTEGER NOT NULL
		REFERENCES region(region_id) ON DELETE RESTRICT,
	content BLOB NOT NULL DEFAULT '',
	content_len INTEGER DEFAULT 0);

CREATE VIEW IF NOT EXISTS region_view AS
	SELECT core_id, region_id, x, y, processor, local_region_index, address,
		content, content_len, fetches, append_time,
		(fetches > 1) AS have_extra
FROM core NATURAL JOIN region;

CREATE VIEW IF NOT EXISTS extra_view AS
    SELECT core_id, region_id, extra_id, x, y, processor, local_region_index,
    	address, append_time, region_extra.content AS content,
    	region_extra.content_len AS content_len
FROM core NATURAL JOIN region NATURAL JOIN region_extra;

-- Information about how to access the connection proxying
-- WARNING! May include credentials
CREATE TABLE IF NOT EXISTS proxy_configuration(
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    value TEXT NOT NULL);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for power provenance
-- Except for engery used by cores or routers
CREATE TABLE IF NOT EXISTS power_provenance(
    power_id INTEGER PRIMARY KEY AUTOINCREMENT,
    description STRING NOT NULL,
    the_value FLOAT NOT NULL);


-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for data speed up packet gathers
CREATE TABLE IF NOT EXISTS gatherer_provenance(
    gather_id INTEGER PRIMARY KEY AUTOINCREMENT,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    address INTEGER NOT NULL,
    bytes INTEGER NOT NULL,
    run INTEGER NOT NULL,
    description STRING NOT NULL,
    the_value FLOAT NOT NULL);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for monitors
CREATE TABLE IF NOT EXISTS monitor_provenance(
    monitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    the_value FLOAT NOT NULL,
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
    cp_id INTEGER PRIMARY KEY AUTOINCREMENT,
	core_id INTEGER NOT NULL
		REFERENCES core(core_id) ON DELETE RESTRICT,
    description STRING NOT NULL,
    the_value INTEGER NOT NULL);


-- Create a view combining core name and data
CREATE VIEW IF NOT EXISTS core_provenance_view AS
    SELECT core_name, x, y, processor as p, description, the_value
    FROM core_provenance NATURAL JOIN core;

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
-- A table connector provenance
CREATE TABLE IF NOT EXISTS connector_provenance(
    connector_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pre_population STRING NOT NULL,
    post_population STRING NOT NULL,
    the_type  STRING NOT NULL,
    description STRING NOT NULL,
    the_value INTEGER NOT NULL);

---------------------------------------------------------------------
-- A table to store job.info
CREATE TABLE IF NOT EXISTS boards_provenance(
    board_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_addres STRING NOT NULL,
    ethernet_x INTEGER NOT NULL,
    ethernet_y INTEGER NOT NULL);
