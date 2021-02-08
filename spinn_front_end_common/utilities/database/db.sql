-- Copyright (c) 2017-2019 The University of Manchester
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

-- We want foreign key enforcement; it should be default on, but it isn't for
-- messy historical reasons.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS configuration_parameters(
    parameter_id TEXT,
    value REAL,
    PRIMARY KEY (parameter_id));

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
    avilableSDRAM INTEGER,
    ip_address INTEGER,
    nearest_ethernet_x INTEGER,
    nearest_ethernet_y INTEGER,
    PRIMARY KEY (chip_x, chip_y, machine_id),
    FOREIGN KEY (machine_id)
        REFERENCES Machine_layout(machine_id));

-- An atomic processing element
CREATE TABLE IF NOT EXISTS Processor(
    chip_x INTEGER,
    chip_y INTEGER,
    machine_id INTEGER,
    available_DTCM INTEGER,
    available_CPU INTEGER,
    physical_id INTEGER,
    PRIMARY KEY (chip_x, chip_y, machine_id, physical_id),
    FOREIGN KEY (chip_x, chip_y, machine_id)
        REFERENCES Machine_chip(chip_x, chip_y, machine_id));

-- One unit of computation at the application level
CREATE TABLE IF NOT EXISTS Application_vertices(
    vertex_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vertex_label TEXT,
    vertex_class TEXT,
    no_atoms INTEGER,
    max_atom_constrant INTEGER);

-- A communication link between two application vertices
CREATE TABLE IF NOT EXISTS Application_edges(
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pre_vertex INTEGER,
    post_vertex INTEGER,
    edge_label TEXT,
    edge_class TEXT,
    FOREIGN KEY (pre_vertex)
        REFERENCES Application_vertices(vertex_id),
    FOREIGN KEY (post_vertex)
        REFERENCES Application_vertices(vertex_id));

-- The edge identified by edge_id starts at the vertex identified by vertex_id
CREATE TABLE IF NOT EXISTS Application_graph(
    vertex_id INTEGER,
    edge_id INTEGER,
    PRIMARY KEY (vertex_id, edge_id),
    FOREIGN KEY (vertex_id)
        REFERENCES Application_vertices(vertex_id),
    FOREIGN KEY (edge_id)
        REFERENCES Application_edges(edge_id));

-- One unit of computation at the system level; deploys to one processor
CREATE TABLE IF NOT EXISTS Machine_vertices(
    vertex_id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT,
    class TEXT,
    cpu_used INTEGER,
    sdram_used INTEGER,
    dtcm_used INTEGER);

-- A communication link between two machine vertices
CREATE TABLE IF NOT EXISTS Machine_edges(
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pre_vertex INTEGER,
    post_vertex INTEGER,
    label TEXT,
    class TEXT,
    FOREIGN KEY (pre_vertex)
        REFERENCES Machine_vertices(vertex_id),
    FOREIGN KEY (post_vertex)
        REFERENCES Machine_vertices(vertex_id));

-- The edge identified by edge_id starts at the vertex identified by vertex_id
CREATE TABLE IF NOT EXISTS Machine_graph(
    vertex_id INTEGER,
    edge_id INTEGER,
    PRIMARY KEY (vertex_id, edge_id),
    FOREIGN KEY (vertex_id)
        REFERENCES Machine_vertices(vertex_id),
    FOREIGN KEY (edge_id)
        REFERENCES Machine_edges(edge_id));

-- The state of the graph mapper, which links each application vertex to a
-- number of machine vertexes, with contiguous-but-non-overlapping ranges of
-- atoms.
CREATE TABLE IF NOT EXISTS graph_mapper_vertex(
    application_vertex_id INTEGER,
    machine_vertex_id INTEGER,
    lo_atom INTEGER,
    hi_atom INTEGER,
    PRIMARY KEY (application_vertex_id, machine_vertex_id),
    FOREIGN KEY (machine_vertex_id)
        REFERENCES Machine_vertices(vertex_id),
    FOREIGN KEY (application_vertex_id)
        REFERENCES Application_vertices(vertex_id));

-- The state of the graph mapper, which links each application edge to one or
-- more machine edges.
CREATE TABLE IF NOT EXISTS graph_mapper_edges(
    application_edge_id INTEGER,
    machine_edge_id INTEGER,
    PRIMARY KEY (application_edge_id, machine_edge_id),
    FOREIGN KEY (machine_edge_id)
        REFERENCES Machine_edges(edge_id),
    FOREIGN KEY (application_edge_id)
        REFERENCES Application_edges(edge_id));

-- How the machine vertices are actually placed on the SpiNNaker machine.
CREATE TABLE IF NOT EXISTS Placements(
    vertex_id INTEGER PRIMARY KEY,
    machine_id INTEGER,
    chip_x INTEGER,
    chip_y INTEGER,
    chip_p INTEGER,
    FOREIGN KEY (vertex_id)
        REFERENCES Machine_vertices(vertex_id),
    FOREIGN KEY (chip_x, chip_y, chip_p, machine_id)
        REFERENCES Processor(chip_x, chip_y, physical_id, machine_id));

-- The mapping of machine edges to the keys and masks used in SpiNNaker
-- packets.
CREATE TABLE IF NOT EXISTS Routing_info(
    edge_id INTEGER,
    "key" INTEGER,
    mask INTEGER,
    PRIMARY KEY (edge_id, "key", mask),
    FOREIGN KEY (edge_id)
        REFERENCES Machine_edges(edge_id));

-- The computed routing table for a chip.
CREATE TABLE IF NOT EXISTS Routing_table(
    chip_x INTEGER,
    chip_y INTEGER,
    position INTEGER,
    key_combo INTEGER,
    mask INTEGER,
    route INTEGER,
    PRIMARY KEY (chip_x, chip_y, position));

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

CREATE TABLE IF NOT EXISTS Reverse_IP_tags(
    vertex_id INTEGER PRIMARY KEY,
    tag INTEGER,
    board_address TEXT,
    port INTEGER,
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
    app_vtx.vertex_label AS label,
    app_vtx.vertex_class AS class
FROM event_to_atom_mapping AS e_to_a
    NATURAL JOIN Application_vertices AS app_vtx;

CREATE VIEW IF NOT EXISTS app_output_tag_view AS SELECT
    IP_tags.ip_address AS ip_address,
    IP_tags.port AS port,
    IP_tags.strip_sdp AS strip_sdp,
    IP_tags.board_address AS board_address,
    IP_tags.tag AS tag,
    pre_vertices.vertex_label AS pre_vertex_label,
    pre_vertices.vertex_class AS pre_vertex_class,
    post_vertices.vertex_label AS post_vertex_label,
    post_vertices.vertex_class AS post_vertex_class
FROM IP_tags
    JOIN graph_mapper_vertex AS mapper
        ON IP_tags.vertex_id = mapper.machine_vertex_id
    JOIN Application_vertices AS post_vertices
        ON mapper.application_vertex_id = post_vertices.vertex_id
    JOIN Application_edges AS edges
        ON mapper.application_vertex_id = edges.post_vertex
    JOIN Application_vertices AS pre_vertices
        ON edges.pre_vertex = pre_vertices.vertex_id;

CREATE VIEW IF NOT EXISTS machine_output_tag_view AS SELECT
    IP_tags.ip_address AS ip_address,
    IP_tags.port AS port,
    IP_tags.strip_sdp AS strip_sdp,
    IP_tags.board_address AS board_address,
    IP_tags.tag AS tag,
    pre_vertices.label AS pre_vertex_label,
    pre_vertices.class AS pre_vertex_class,
    post_vertices.label AS post_vertex_label,
    post_vertices.class AS post_vertex_class
FROM IP_tags
    JOIN Machine_vertices AS post_vertices
        ON IP_tags.vertex_id = post_vertices.vertex_id
    JOIN Machine_edges AS edges
        ON edges.post_vertex = post_vertices.vertex_id
    JOIN Machine_vertices AS pre_vertices
        ON edges.pre_vertex = pre_vertices.vertex_id;

CREATE VIEW IF NOT EXISTS app_input_tag_view AS SELECT
    Reverse_IP_tags.board_address AS board_address,
    Reverse_IP_tags.port AS port,
    application.vertex_label AS application_label,
    application.vertex_class AS application_class
FROM Reverse_IP_tags
    JOIN graph_mapper_vertex AS mapper
        ON Reverse_IP_tags.vertex_id = mapper.machine_vertex_id
    JOIN Application_vertices AS application
        ON mapper.application_vertex_id = application.vertex_id;

CREATE VIEW IF NOT EXISTS machine_input_tag_view AS SELECT
    Reverse_IP_tags.board_address AS board_address,
    Reverse_IP_tags.port AS port,
    post_vertices.label AS machine_label,
    post_vertices.class AS machine_class
FROM Reverse_IP_tags
    JOIN Machine_vertices AS post_vertices
        ON Reverse_IP_tags.vertex_id = post_vertices.vertex_id;

CREATE VIEW IF NOT EXISTS machine_edge_key_view AS SELECT
    Routing_info."key" AS "key",
    Routing_info.mask AS mask,
    pre_vertices.label AS pre_vertex_label,
    pre_vertices.class AS pre_vertex_class,
    post_vertices.label AS post_vertex_label,
    post_vertices.class AS post_vertex_class
FROM Routing_info
    JOIN Machine_edges
        ON Machine_edges.edge_id = Routing_info.edge_id
    JOIN Machine_vertices AS post_vertices
        ON post_vertices.vertex_id = Machine_edges.post_vertex
    JOIN Machine_vertices AS pre_vertices
        ON pre_vertices.vertex_id = Machine_edges.pre_vertex;

CREATE VIEW IF NOT EXISTS machine_vertex_placement AS SELECT
    Placements.chip_x AS x,
    Placements.chip_y AS y,
    Placements.chip_p AS p,
    Machine_vertices.label AS vertex_label,
    Machine_vertices.class AS vertex_class
FROM Placements
    NATURAL JOIN Machine_vertices;

CREATE VIEW IF NOT EXISTS application_vertex_placements AS SELECT
    Placements.chip_x AS x,
    Placements.chip_y AS y,
    Placements.chip_p AS p,
    Application_vertices.vertex_label AS vertex_label,
    Application_vertices.vertex_class AS vertex_class
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
