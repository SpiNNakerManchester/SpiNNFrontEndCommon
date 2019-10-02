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
-- A table describing the cores.
CREATE TABLE IF NOT EXISTS core(
    core_id INTEGER PRIMARY KEY AUTOINCREMENT,
	x INTEGER NOT NULL,
	y INTEGER NOT NULL,
	processor INTEGER NOT NULL);
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
	content BLOB NOT NULL DEFAULT X'',
	have_extra INTEGER NOT NULL DEFAULT 0,
	fetches INTEGER NOT NULL DEFAULT 0,
	append_time INTEGER);
-- Every recording region has a unique vertex and index
CREATE UNIQUE INDEX IF NOT EXISTS regionSanity ON region(
	core_id ASC, local_region_index ASC);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table containing the data which doesn't fit in the content column of the
-- region table; care must be taken with this to not exceed 1GB!
CREATE TABLE IF NOT EXISTS region_extra(
	extra_id INTEGER PRIMARY KEY ASC AUTOINCREMENT,
	region_id INTEGER NOT NULL
		REFERENCES region(region_id) ON DELETE RESTRICT,
	content BLOB NOT NULL DEFAULT X'');

CREATE VIEW IF NOT EXISTS region_view AS
	SELECT core_id, region_id, x, y, processor, local_region_index, address,
		content, fetches, append_time, have_extra
FROM core NATURAL JOIN region;
