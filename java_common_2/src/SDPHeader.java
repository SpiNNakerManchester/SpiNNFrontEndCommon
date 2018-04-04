public class SDPHeader {
	private final byte destination_chip_x;
	private final byte destination_chip_y;
	private final byte destination_chip_p;
	private final byte destination_port;
	private final byte flags;
	private final byte tag;
	private final byte source_port;
	private final byte source_cpu;
	private final byte source_chip_x;
	private final byte source_chip_y;
	private final int length = 10;

	private static final byte toByte(int x) {
		return (byte) (x & 0xFF);
	}

	public SDPHeader(int destination_chip_x, int destination_chip_y,
			int destination_chip_p, int destination_port, int flags, int tag,
			int source_port, int source_cpu, int source_chip_x,
			int source_chip_y) {
		this.destination_chip_x = toByte(destination_chip_x);
		this.destination_chip_y = toByte(destination_chip_y);
		this.destination_chip_p = toByte(destination_chip_p);
		this.destination_port = toByte(destination_port);
		this.flags = toByte(flags);
		this.tag = toByte(tag);
		this.source_port = toByte(source_port);
		this.source_cpu = toByte(source_cpu);
		this.source_chip_x = toByte(source_chip_x);
		this.source_chip_y = toByte(source_chip_y);
	}

	byte[] convert_byte_array() {
		byte[] message_data = new byte[length];

		message_data[0] = 0;
		message_data[1] = 0;
		message_data[2] = flags;
		message_data[3] = tag;

		// Compose Dest_port+cpu = 3 MSBs as port and 5 LSBs as cpu
		message_data[4] = toByte(
				((destination_port & 7) << 5) | (destination_chip_p & 31));

		// Compose Source_port+cpu = 3 MSBs as port and 5 LSBs as cpu
		message_data[5] = toByte(((source_port & 7) << 5) | (source_cpu & 31));
		message_data[6] = destination_chip_y;
		message_data[7] = destination_chip_x;
		message_data[8] = source_chip_y;
		message_data[9] = source_chip_x;

		return message_data;
	}

	int length() {
		return length;
	}
}
