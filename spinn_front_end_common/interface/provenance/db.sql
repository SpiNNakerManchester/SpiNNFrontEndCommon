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
-- A table holding the values for versions
CREATE TABLE IF NOT EXISTS version_provenance(
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    description STRING NOT NULL,
    the_value STRING NOT NULL);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for power provenance
-- Except for engery used by cores or routers
CREATE TABLE IF NOT EXISTS power_provenance(
    power_id INTEGER PRIMARY KEY AUTOINCREMENT,
    description STRING NOT NULL,
    the_value FLOAT NOT NULL);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for algorithm timings
CREATE TABLE IF NOT EXISTS timer_provenance(
    timer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category STRING NOT NULL,
    algorithm STRING NOT NULL,
    the_value INTEGER NOT NULL,
    n_run INTEGER NOT NULL,
    n_loop INTEGER,
    skip_reason STRING);

CREATE VIEW IF NOT EXISTS timer_view AS
    SELECT category, algorithm, the_value, n_run, n_loop
    FROM timer_provenance
    WHERE skip_reason is NULL
    ORDER BY timer_id;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for category timings
CREATE TABLE IF NOT EXISTS category_timer_provenance(
    timer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category STRING NOT NULL,
    the_value INTEGER NOT NULL,
    n_run INTEGER,
    n_loop INTEGER);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for uncategorised general provenance
CREATE TABLE IF NOT EXISTS other_provenance(
    other_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category STRING NOT NULL,
    description STRING NOT NULL,
    the_value STRING NOT NULL);

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

-- Create a view combining core name and data
CREATE VIEW IF NOT EXISTS core_provenance_view AS
    SELECT core_name, x, y, p, description, the_value
    FROM core_provenance NATURAL JOIN core_mapping;

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
