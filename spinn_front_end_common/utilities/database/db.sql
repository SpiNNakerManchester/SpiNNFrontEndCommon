-- Copyright (c) 2017 The University of Manchester
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

-- We want foreign key enforcement; it should be default on, but it isn't for
-- messy historical reasons.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS configuration_parameters(
    parameter_id TEXT,
    value REAL,
    PRIMARY KEY (parameter_id));

-- Information about how to access the connection proxying
-- WARNING! May include credentials
CREATE TABLE IF NOT EXISTS proxy_configuration(
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS Machine_layout(
    machine_id INTEGER PRIMARY KEY AUTOINCREMENT,
    x_dimension INTEGER,
    y_dimension INTEGER);

-- A collection of processors
CREATE TABLE IF NOT EXISTS Machine_chip(
    no_processors INTEGER,
    chip_x INTEGER,
    chip_y INTEGER,
    machine_id INTEGER,
    ip_address INTEGER,
    nearest_ethernet_x INTEGER,
    nearest_ethernet_y INTEGER,
    PRIMARY KEY (chip_x, chip_y, machine_id),
    FOREIGN KEY (machine_id)
        REFERENCES Machine_layout(machine_id));

-- One unit of computation at the application level
CREATE TABLE IF NOT EXISTS Application_vertices(
    vertex_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vertex_label TEXT);

-- One unit of computation at the system level; deploys to one processor
CREATE TABLE IF NOT EXISTS Machine_vertices(
    vertex_id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT);

-- The state of the graph mapper, which links each application vertex to a
-- number of machine vertexes, with contiguous-but-non-overlapping ranges of
-- atoms.
CREATE TABLE IF NOT EXISTS graph_mapper_vertex(
    application_vertex_id INTEGER,
    machine_vertex_id INTEGER,
    PRIMARY KEY (application_vertex_id, machine_vertex_id),
    FOREIGN KEY (machine_vertex_id)
        REFERENCES Machine_vertices(vertex_id),
    FOREIGN KEY (application_vertex_id)
        REFERENCES Application_vertices(vertex_id));

-- How the machine vertices are actually placed on the SpiNNaker machine.
CREATE TABLE IF NOT EXISTS Placements(
    vertex_id INTEGER PRIMARY KEY,
    machine_id INTEGER,
    chip_x INTEGER,
    chip_y INTEGER,
    chip_p INTEGER,
    FOREIGN KEY (vertex_id)
        REFERENCES Machine_vertices(vertex_id),
    FOREIGN KEY (chip_x, chip_y, machine_id)
        REFERENCES Machine_chip(chip_x, chip_y, machine_id));

-- A map of which machine vertex is connected to which LPG vertex
CREATE TABLE IF NOT EXISTS m_vertex_to_lpg_vertex(
    pre_vertex_id INTEGER,
    partition_id TEXT,
    post_vertex_id INTEGER,
    PRIMARY KEY (pre_vertex_id, partition_id, post_vertex_id)
    FOREIGN KEY (pre_vertex_id)
        REFERENCES Machine_vertices(vertex_id),
    FOREIGN KEY (post_vertex_id)
        REFERENCES Machine_vertices(vertex_id));

CREATE TABLE IF NOT EXISTS IP_tags(
    vertex_id INTEGER,
    tag INTEGER,
    board_address TEXT,
    ip_address TEXT,
    port INTEGER,
    strip_sdp BOOLEAN,
    PRIMARY KEY (vertex_id, tag, board_address, ip_address, port, strip_sdp),
    FOREIGN KEY (vertex_id)
        REFERENCES Machine_vertices(vertex_id));

CREATE TABLE IF NOT EXISTS event_to_atom_mapping(
    vertex_id INTEGER,
    atom_id INTEGER,
    event_id INTEGER PRIMARY KEY,
    FOREIGN KEY (vertex_id)
        REFERENCES Machine_vertices(vertex_id));

-- Views that simplify common queries

CREATE VIEW IF NOT EXISTS label_event_atom_view AS SELECT
    e_to_a.atom_id AS atom,
    e_to_a.event_id AS event,
    app_vtx.vertex_label AS label
FROM event_to_atom_mapping AS e_to_a
    JOIN Machine_vertices as machine_vertices
        ON e_to_a.vertex_id == machine_vertices.vertex_id
    JOIN graph_mapper_vertex as mapper
        ON machine_vertices.vertex_id == mapper.machine_vertex_id
    JOIN Application_vertices AS app_vtx
        ON mapper.application_vertex_id == app_vtx.vertex_id;

CREATE VIEW IF NOT EXISTS app_output_tag_view AS SELECT
    IP_tags.ip_address AS ip_address,
    IP_tags.port AS port,
    IP_tags.strip_sdp AS strip_sdp,
    IP_tags.board_address AS board_address,
    IP_tags.tag AS tag,
    pre_app_vertices.vertex_label AS pre_vertex_label,
    lpg_vertices.label AS post_vertex_label,
    lpg_placements.chip_x AS chip_x,
    lpg_placements.chip_y AS chip_y
FROM m_vertex_to_lpg_vertex
    JOIN IP_Tags
        ON m_vertex_to_lpg_vertex.post_vertex_id = IP_tags.vertex_id
    JOIN Machine_vertices AS lpg_vertices
        ON m_vertex_to_lpg_vertex.post_vertex_id = lpg_vertices.vertex_id
    JOIN graph_mapper_vertex AS pre_mapper
        ON m_vertex_to_lpg_vertex.pre_vertex_id = pre_mapper.machine_vertex_id
    JOIN Application_vertices AS pre_app_vertices
        ON pre_mapper.application_vertex_id = pre_app_vertices.vertex_id
    JOIN Placements AS lpg_placements
        ON lpg_placements.vertex_id = lpg_vertices.vertex_id;

CREATE VIEW IF NOT EXISTS application_vertex_placements AS SELECT
    Placements.chip_x AS x,
    Placements.chip_y AS y,
    Placements.chip_p AS p,
    Application_vertices.vertex_label AS vertex_label
FROM Placements
    JOIN graph_mapper_vertex
        ON Placements.vertex_id = graph_mapper_vertex.machine_vertex_id
    JOIN Application_vertices
        ON graph_mapper_vertex.application_vertex_id = Application_vertices.vertex_id;

CREATE VIEW IF NOT EXISTS chip_eth_info AS SELECT
    chip.chip_x AS x,
    chip.chip_y AS y,
    eth_chip.chip_x AS eth_x,
    eth_chip.chip_y AS eth_y,
    eth_chip.ip_address AS eth_ip_address
FROM Machine_chip AS chip
    JOIN Machine_chip AS eth_chip
        ON  chip.nearest_ethernet_x = eth_chip.chip_x
        AND chip.nearest_ethernet_y = eth_chip.chip_y;
