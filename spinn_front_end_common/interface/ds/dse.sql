-- Copyright (c) 2018 The University of Manchester
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


-- This file should be a clone of
-- JavaSpiNNaker/SpiNNaker-storage/src/main/resources/dse.sql

PRAGMA main.synchronous = OFF;
-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing the boards.
CREATE TABLE IF NOT EXISTS board(
	board_id INTEGER PRIMARY KEY AUTOINCREMENT,
	ethernet_x INTEGER NOT NULL,
	ethernet_y INTEGER NOT NULL,
	address TEXT UNIQUE NOT NULL);
-- Every board has a unique ethernet chip location in virtual space.
CREATE UNIQUE INDEX IF NOT EXISTS boardSanity ON board(
	ethernet_x ASC, ethernet_y ASC);


-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
-- A table describing the cores and the DSE info to write to them.
CREATE TABLE IF NOT EXISTS core(
    core_id INTEGER PRIMARY KEY AUTOINCREMENT,
	x INTEGER NOT NULL,
	y INTEGER NOT NULL,
	processor INTEGER NOT NULL,
	board_id INTEGER NOT NULL
		REFERENCES board(board_id) ON DELETE RESTRICT,
	app_id INTEGER,
	content BLOB,
	start_address INTEGER,
	memory_used INTEGER,
	memory_written INTEGER);
-- Every processor has a unique ID
CREATE UNIQUE INDEX IF NOT EXISTS coreSanity ON core(
	x ASC, y ASC, processor ASC);

CREATE VIEW IF NOT EXISTS core_view AS
	SELECT board_id, core_id,
		ethernet_x, ethernet_y, board.address AS ethernet_address,
		x, y, processor, app_id, content,
		start_address, memory_used, memory_written
FROM board NATURAL JOIN core;