import static java.lang.System.arraycopy;

public class SDPMessage {
    public static final int MAX_PACKET_SIZE = 300;
    public static final int MAX_PACKET_SIZE_DATA = 292;
    public static final int REPLY_NOT_EXPECTED = 0x07;
    public static final int REPLY_EXPECTED = 0x87;

    private final byte[] data;
    private final SDPHeader header;

    public SDPMessage(
            int destination_chip_x, int destination_chip_y,
            int destination_chip_p, int destination_port, int flags, int tag,
            int source_port, int source_cpu, int source_chip_x,
            int source_chip_y, byte[] data) {
        this.data = data;
        header = new SDPHeader(
            destination_chip_x, destination_chip_y, destination_chip_p, 
            destination_port, flags, tag, source_port, source_cpu, 
            source_chip_x, source_chip_y);
    }

    byte[] convert_to_byte_array() {
        byte[] message_data = new byte[header.length() + data.length];
        arraycopy(header.convert_byte_array(), 0, message_data, 0,
                  header.length());
        arraycopy(data, 0, message_data, header.length(), data.length);
        return message_data;
    }

    int length_in_bytes() {
        return data.length + header.length();
    }
}
