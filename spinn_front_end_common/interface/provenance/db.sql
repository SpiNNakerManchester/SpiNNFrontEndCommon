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
-- A table assigning ids to vertex names
CREATE TABLE IF NOT EXISTS vertex(
  vertex_id INTEGER PRIMARY KEY AUTOINCREMENT,
	vertex_name STRING NOT NULL);

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table assigning ids to description names
CREATE TABLE IF NOT EXISTS description(
  description_id INTEGER PRIMARY KEY AUTOINCREMENT,
	description_name STRING NOT NULL);


-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table holding the values
CREATE TABLE IF NOT EXISTS provenance(
  provenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
  vertex_id INTEGER NOT NULL,
  description_id INTEGER NOT NULL,
	the_value INTEGER NOT NULL);


CREATE VIEW IF NOT EXISTS provenance_view AS
    SELECT vertex_id, description_id, provenance_id, vertex_name, description_name, the_value
    FROM vertex NATURAL JOIN description NATURAL JOIN provenance;

CREATE VIEW IF NOT EXISTS stats_view AS
    SELECT description_name, min(the_value) as min, max(the_value) as max, avg(the_value) as avg, sum(the_value) as total, count(the_value) as count
    FROM description NATURAL JOIN provenance
    group by description_name
