-- We want foreign key enforcement; it should be default on, but it isn't for
-- messy historical reasons.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS configuration_parameters(
	parameter_id TEXT,
	value REAL,
	PRIMARY KEY (parameter_id));

CREATE TABLE IF NOT EXISTS Machine_layout(
	machine_id INTEGER PRIMARY KEY AUTOINCREMENT,
	x_dimension INT,
	y_dimension INT);

-- A collection of processors
CREATE TABLE IF NOT EXISTS Machine_chip(
	no_processors INT,
	chip_x INTEGER,
	chip_y INTEGER,
	machine_id INTEGER,
	avilableSDRAM INT,
	PRIMARY KEY (chip_x, chip_y, machine_id),
	FOREIGN KEY (machine_id)
		REFERENCES Machine_layout(machine_id));

-- An atomic processing element
CREATE TABLE IF NOT EXISTS Processor(
	chip_x INTEGER,
	chip_y INTEGER,
	machine_id INTEGER,
	available_DTCM INT,
	available_CPU INT,
	physical_id INTEGER,
	PRIMARY KEY (chip_x, chip_y, machine_id, physical_id),
	FOREIGN KEY (chip_x, chip_y, machine_id)
		REFERENCES Machine_chip(chip_x, chip_y, machine_id));

-- One unit of computation at the application level
CREATE TABLE IF NOT EXISTS Application_vertices(
	vertex_id INTEGER PRIMARY KEY AUTOINCREMENT,
	vertex_label TEXT,
	no_atoms INT,
	max_atom_constrant INT,
	recorded INT);

-- A communication link between two application vertices
CREATE TABLE IF NOT EXISTS Application_edges(
	edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
	pre_vertex INTEGER,
	post_vertex INTEGER,
	edge_label TEXT,
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
	cpu_used INT,
	sdram_used INT,
	dtcm_used INT);

-- A communication link between two machine vertices
CREATE TABLE IF NOT EXISTS Machine_edges(
	edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
	pre_vertex INTEGER,
	post_vertex INTEGER,
	label TEXT,
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
	lo_atom INT,
	hi_atom INT,
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
	chip_x INT,
	chip_y INT,
	chip_p INT,
	FOREIGN KEY (vertex_id)
		REFERENCES Machine_vertices(vertex_id),
	FOREIGN KEY (chip_x, chip_y, chip_p, machine_id)
		REFERENCES Processor(chip_x, chip_y, physical_id, machine_id));

-- The mapping of machine edges to the keys and masks used in SpiNNaker
-- packets.
CREATE TABLE IF NOT EXISTS Routing_info(
	edge_id INTEGER,
	"key" INT,
	mask INT,
	PRIMARY KEY (edge_id, "key", mask),
	FOREIGN KEY (edge_id)
		REFERENCES Machine_edges(edge_id));

-- The computed routing table for a chip.
CREATE TABLE IF NOT EXISTS Routing_table(
	chip_x INTEGER,
	chip_y INTEGER,
	position INTEGER,
	key_combo INT,
	mask INT,
	route INT,
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
