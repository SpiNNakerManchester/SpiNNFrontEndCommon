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
-- A table holding the values for versions
CREATE TABLE IF NOT EXISTS version_provenance(
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    description STRING NOT NULL,
    the_value STRING NOT NULL);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for algorithm timings
CREATE TABLE IF NOT EXISTS timer_provenance(
    timer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    algorithm STRING NOT NULL,
    work STRING NOT NULL,
    time_taken INTEGER NOT NULL,
    skip_reason STRING);

CREATE VIEW IF NOT EXISTS full_timer_view AS
    SELECT timer_id, category, algorithm, work, machine_on, timer_provenance.time_taken, n_run, n_loop, skip_reason
    FROM timer_provenance ,category_timer_provenance
	WHERE timer_provenance.category_id = category_timer_provenance.category_id
    ORDER BY timer_id;

CREATE VIEW IF NOT EXISTS timer_view AS
    SELECT category, algorithm, work, machine_on, time_taken, n_run, n_loop
    FROM full_timer_view
    WHERE skip_reason is NULL
    ORDER BY timer_id;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values for category timings
CREATE TABLE IF NOT EXISTS category_timer_provenance(
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category STRING NOT NULL,
    time_taken INTEGER,
    machine_on BOOL NOT NULL,
    n_run INTEGER NOT NULL,
    n_loop INTEGER);

---------------------------------------------------------------------
-- A table to store log.info
CREATE TABLE IF NOT EXISTS p_log_provenance(
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    level INTEGER NOT NULL,
    message STRING NOT NULL);

CREATE TABLE IF NOT EXISTS log_level_names(
    level INTEGER PRIMARY KEY NOT NULL,
    name STRING NOT NULL);

INSERT OR IGNORE INTO log_level_names
    (level, name)
VALUES
    (50, "CRITICAL"),
    (40, "ERROR"),
    (30, "WARNING"),
    (20, "INFO"),
    (10, "DEBUG");

CREATE VIEW IF NOT EXISTS p_log_view AS
    SELECT
        timestamp,
		name,
        message
    FROM p_log_provenance left join log_level_names
    ON p_log_provenance.level = log_level_names.level
    ORDER BY p_log_provenance.log_id;
