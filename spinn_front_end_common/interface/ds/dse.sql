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


-- This file should be a clone of
-- JavaSpiNNaker/SpiNNaker-storage/src/main/resources/dse.sql

-- https://www.sqlite.org/pragma.html#pragma_synchronous
PRAGMA main.synchronous = OFF;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing the ethernets.
CREATE TABLE IF NOT EXISTS ethernet(
    ethernet_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ethernet_x INTEGER NOT NULL,
    ethernet_y INTEGER NOT NULL,
    ip_address TEXT UNIQUE NOT NULL);
-- Every ethernet has a unique chip location in virtual space.
CREATE UNIQUE INDEX IF NOT EXISTS ethernetSanity ON ethernet(
    ethernet_x ASC, ethernet_y ASC);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing the chips and their ethernet.
CREATE TABlE IF NOT EXISTS chip(
    chip_id INTEGER PRIMARY KEY AUTOINCREMENT,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    ethernet_id INTEGER NOT NULL
        REFERENCES ethernet(ethernet_id) ON DELETE RESTRICT
);
-- Every chip has a unique ID
CREATE UNIQUE INDEX IF NOT EXISTS chipSanity ON chip(
    x ASC, y ASC);

CREATE VIEW IF NOT EXISTS chip_view AS
    SELECT chip_id, x, y, ethernet_x, ethernet_y, ip_address
    FROM ethernet NATURAL JOIN chip;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing the cores.
CREATE TABLE IF NOT EXISTS core(
    core_id INTEGER PRIMARY KEY AUTOINCREMENT,
    chip_id INTEGER NOT NULL REFERENCES chip(chip_id) ON DELETE RESTRICT,
    processor INTEGER NOT NULL,
    is_system INTEGER NOT NULL,
    base_address INTEGER);
-- Every processor has a unique ID
CREATE UNIQUE INDEX IF NOT EXISTS coreSanity ON core(
    chip_id ASC, processor ASC);

CREATE VIEW IF NOT EXISTS core_view AS
    SELECT core_id, x, y, processor, base_address, is_system,
           ethernet_x, ethernet_y, ip_address
    FROM core NATURAL JOIN chip_view;

CREATE VIEW IF NOT EXISTS core_memory_view AS
    SELECT core_id, sum(size) as regions_size, sum(size) + 392 as memory_used
	FROM region
	GROUP BY core_id;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing the regions.
CREATE TABLE IF NOT EXISTS region(
    region_id INTEGER PRIMARY KEY,
    region_num INTEGER NOT NULL,
    core_id INTEGER NOT NULL REFERENCES core(core_id) ON DELETE RESTRICT,
    reference_num INTEGER,
    size INT NOT NULL,
    pointer INTEGER,
    region_label TEXT);
-- Every region has a unique ID
CREATE UNIQUE INDEX IF NOT EXISTS region_sanity ON region(
   core_id ASC, region_num ASC);
CREATE UNIQUE INDEX IF NOT EXISTS region_reference_sanity ON region(
    reference_num ASC);

CREATE VIEW IF NOT EXISTS region_view AS
    SELECT region_id, x, y, processor, base_address, is_system,
           region_num, region_label, reference_num, size, pointer,
           core_id
    FROM core_view NATURAL JOIN region;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing the data to write.
CREATE TABLE IF NOT EXISTS write (
    write_id  INTEGER PRIMARY KEY,
    region_id INTEGER NOT NULL,
    write_data BLOB NOT NULL,
    offset INTEGER NOT NULL,
    data_debug TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS write_sanity ON write(
   region_id ASC, offset ASC);

CREATE VIEW IF NOT EXISTS write_view AS
    SELECT region_id, x, y, processor, region_num, region_label, size, pointer,
           offset, write_data, length(write_data) as data_size, data_debug,
           core_id
    FROM region_view NATURAL JOIN write;

CREATE VIEW IF NOT EXISTS write_too_big AS
    SELECT *
    FROM write_view
    WHERE length(write_data) > size;

CREATE VIEW IF NOT EXISTS core_write_view AS
    SELECT core_id, sum(length(write_data)) as region_written, sum(length(write_data)) +392 as memory_written
    FROM region NATURAL JOIN write
	GROUP BY core_id;

CREATE VIEW IF NOT EXISTS core_info AS
    SELECT core.core_id, x, y, processor, base_address,
           regions_size, memory_used, region_written, memory_written
    FROM core
        NATURAL JOIN chip
        LEFT JOIN core_memory_view
            on core.core_id = core_memory_view.core_id
        LEFT JOIN core_write_view
            on core.core_id = core_write_view.core_id;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing the references.
CREATE TABLE IF NOT EXISTS reference (
    reference_id INTEGER PRIMARY KEY,
    reference_num INTEGER NOT NULL,
    region_num INTEGER NOT NULL,
    core_id INTEGER NOT NULL REFERENCES core(core_id) ON DELETE RESTRICT,
    ref_label TEXT);
-- -- Every reference os unique per core
CREATE UNIQUE INDEX IF NOT EXISTS reference_sanity ON reference(
    core_id ASC, region_num ASC);
CREATE UNIQUE INDEX IF NOT EXISTS reference_sanity2 ON reference(
    core_id ASC, reference_num ASC);

CREATE VIEW IF NOT EXISTS reverence_view AS
SELECT reference_id, ref_label, x, y, processor, reference_num
FROM reference
JOIN core_view where reference.core_id = core_view.core_id;

CREATE VIEW IF NOT EXISTS full_reverence_view AS
SELECT reference_id, ref_label, reverence_view.reference_num,
       reverence_view.x as x, reverence_view.y as y, reverence_view.processor as source_p,
       region_view.processor as target_p, region_view.size, region_label, pointer
FROM reverence_view LEFT JOIN region_view
ON reverence_view.reference_num = region_view.reference_num;

CREATE VIEW IF NOT EXISTS broken_reverence_view AS
SELECT * FROM full_reverence_view
WHERE size IS NULL;

CREATE VIEW IF NOT EXISTS non_local_reverence_view AS
SELECT *
FROM reverence_view LEFT JOIN region_view
ON reverence_view.reference_num = region_view.reference_num
WHERE reverence_view.x != region_view.x OR reverence_view.y != region_view.y;

CREATE TABLE IF NOT EXISTS app_id (
    app_id INTEGER NOT NULL
);

-- Information about how to access the connection proxying
-- WARNING! May include credentials
CREATE TABLE IF NOT EXISTS proxy_configuration(
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    value TEXT NOT NULL);
