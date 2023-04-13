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
-- A table describing the cores and the DSE info to write to them.
CREATE TABLE IF NOT EXISTS core(
    core_id INTEGER PRIMARY KEY AUTOINCREMENT,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    processor INTEGER NOT NULL,
    ethernet_id INTEGER NOT NULL
        REFERENCES ethernet(ethernet_id) ON DELETE RESTRICT,
    is_system INTEGER DEFAULT 0,
    app_id INTEGER,
    content BLOB,
    start_address INTEGER,
    memory_used INTEGER,
    memory_written INTEGER);
-- Every processor has a unique ID
CREATE UNIQUE INDEX IF NOT EXISTS coreSanity ON core(
    x ASC, y ASC, processor ASC);

CREATE VIEW IF NOT EXISTS core_view AS
    SELECT ethernet_id, core_id,
        ethernet_x, ethernet_y, ip_address,
        x, y, processor, is_system, app_id, content,
        start_address, memory_used, memory_written
    FROM ethernet NATURAL JOIN core;

-- Information about how to access the connection proxying
-- WARNING! May include credentials
CREATE TABLE IF NOT EXISTS proxy_configuration(
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    value TEXT NOT NULL);
