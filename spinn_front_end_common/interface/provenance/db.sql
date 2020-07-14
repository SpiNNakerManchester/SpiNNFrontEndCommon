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
-- A table assigning ids to sourcex names
CREATE TABLE IF NOT EXISTS source(
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
	source_name STRING UNIQUE NOT NULL);

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
-- Glue the bits together to show the information that people think is here
CREATE VIEW IF NOT EXISTS provenance_view AS
    SELECT source_id, description_id, provenance_id, source_name, description_name, the_value
    FROM source NATURAL JOIN description NATURAL JOIN provenance;

-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- Compute some basic statistics over the provenance
CREATE VIEW IF NOT EXISTS stats_view AS
    SELECT
    	CASE count(DISTINCT source_name)
    	    WHEN 1 THEN source_name
			ELSE ""
		END AS source,
    	description_name AS description,
    	min(the_value) AS min,
    	max(the_value) AS max,
    	avg(the_value) AS avg,
    	sum(the_value) AS total,
    	count(the_value) AS count
    FROM source NATURAL JOIN description NATURAL JOIN provenance
    GROUP BY description;
