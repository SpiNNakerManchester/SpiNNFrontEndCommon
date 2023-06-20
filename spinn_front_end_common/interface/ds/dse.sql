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
PRAGMA foreign_keys = ON;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing the ethernets.
CREATE TABLE IF NOT EXISTS ethernet(
    ethernet_x INTEGER NOT NULL,
    ethernet_y INTEGER NOT NULL,
    ip_address TEXT UNIQUE NOT NULL,
    PRIMARY KEY (ethernet_x, ethernet_y));

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing the chips and their ethernet.
CREATE TABlE IF NOT EXISTS chip(
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    ethernet_x INTEGER NOT NULL,
    ethernet_y INTEGER NOT NULL,
    PRIMARY KEY (x, y),
    FOREIGN KEY (ethernet_x, ethernet_y)
        REFERENCES ethernet(ethernet_x, ethernet_y)
    );

CREATE VIEW IF NOT EXISTS chip_view AS
    SELECT x, y, ethernet_x, ethernet_y, ip_address
    FROM ethernet NATURAL JOIN chip;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing the cores.
CREATE TABLE IF NOT EXISTS core(
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    p INTEGER NOT NULL,
    is_system INTEGER NOT NULL,
    start_address INTEGER,
    memory_written INTEGER,
    PRIMARY KEY (x, y, p),
    FOREIGN KEY (x, y) REFERENCES chip(x, y)
);

CREATE VIEW IF NOT EXISTS core_view AS
    SELECT x, y, p, start_address, is_system,
           ethernet_x, ethernet_y, ip_address
    FROM core NATURAL JOIN chip_view;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing the regions.
CREATE TABLE IF NOT EXISTS region(
    region_num INTEGER NOT NULL,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    p INTEGER NOT NULL,
    reference_num INTEGER,
    content BLOB,
    content_debug TEXT,
    size INT NOT NULL,
    pointer INTEGER,
    region_label TEXT,
    PRIMARY KEY (x, y, p, region_num),
    FOREIGN KEY (x, y, p) REFERENCES core(x, y, p));

-- -- Every reference is unique per core
CREATE UNIQUE INDEX IF NOT EXISTS reference_in_sanity ON region(
    x ASC, Y ASC, p ASC, reference_num ASC);

CREATE VIEW IF NOT EXISTS content_size_view AS
SELECT x,y,p, sum(COALESCE(length(content), 0)) as contents_size
FROM region
GROUP BY x, y, p;

CREATE VIEW IF NOT EXISTS region_size_view AS
SELECT x,y,p, sum(size) as regions_size
FROM region
GROUP BY x, y, p;

CREATE VIEW IF NOT EXISTS region_size_ethernet_view AS
SELECT x,y,p, sum(size) as regions_size, ethernet_x, ethernet_y, is_system
FROM chip NATURAL JOIN core NATURAL JOIN region
GROUP BY x, y, p;

CREATE VIEW IF NOT EXISTS core_summary_view AS
SELECT core.x, core.y, core.p, start_address,
       contents_size, COALESCE(contents_size + 392, 392) as to_write,
       regions_size, COALESCE(regions_size + 392, 392) as malloc_size
FROM core NATURAL JOIN chip
LEFT JOIN content_size_view
ON core.x = content_size_view.x AND core.y = content_size_view.y AND core.p = content_size_view.p
LEFT JOIN region_size_view
ON core.x = region_size_view.x AND core.y = region_size_view.y AND core.p = region_size_view.p;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing the references.
CREATE TABLE IF NOT EXISTS reference (
    reference_num INTEGER NOT NULL,
    region_num INTEGER NOT NULL,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    p INTEGER NOT NULL,
    ref_label TEXT,
    PRIMARY KEY (x, y, p, region_num),
    FOREIGN KEY (x, y, p) REFERENCES core(x, y, p));

-- -- Every reference is unique per core
CREATE UNIQUE INDEX IF NOT EXISTS reference_out_sanity ON reference(
    x ASC, Y ASC, p ASC, reference_num ASC);

CREATE VIEW IF NOT EXISTS linked_reference_view AS
SELECT reference.reference_num, reference.x as x, reference.y as y,
       reference.p as ref_p, reference.region_num as ref_region, ref_label,
       region.p as act_p, region.region_num as act_region, region_label,
       region.size,  pointer
FROM reference LEFT JOIN region
ON reference.reference_num = region.reference_num
    AND reference.x = region.x
    AND reference.y = region.y;

CREATE VIEW IF NOT EXISTS pointer_content_view AS
SELECT x, y, p, region_num, pointer, content FROM
	(SELECT reference.x, reference.y, reference.p, reference.region_num, pointer, NULL as content
	FROM reference LEFT JOIN region
	ON reference.reference_num = region.reference_num
		AND reference.x = region.x
		AND reference.y = region.y)
UNION
SELECT x, y, p, region_num, pointer, content FROM region;

CREATE TABLE IF NOT EXISTS app_id (
    app_id INTEGER NOT NULL
);

-- Information about how to access the connection proxying
-- WARNING! May include credentials
CREATE TABLE IF NOT EXISTS proxy_configuration(
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    value TEXT NOT NULL);
