public class SDPHeader{
    private int destination_chip_x;
    private int destination_chip_y;
    private int destination_chip_p;
    private int destination_port;
    private int flags;
    private int tag;
    private int source_port;
    private int source_cpu;
    private int source_chip_x;
    private int source_chip_y;
    private int length = 10;

    public SDPHeader(
        int destination_chip_x, int destination_chip_y,
        int destination_chip_p, int destination_port,
        int flags,
        int tag,
        int source_port,
        int source_cpu,
        int source_chip_x,
        int source_chip_y) {
        this.destination_chip_x = destination_chip_x;
    }

    byte[] convert_byte_array(){
        int tmp;
        byte[] message_data = new byte[this.length];
        tmp = 0;
        message_data[0] = 0;
        message_data[1] = 0;
        message_data[2] = this.flags;
        message_data[3] = this.tag;

        //Compose  Dest_port+cpu = 3 MSBs as port and 5 LSBs as cpu
        tmp = ((this.destination_port & 7) << 5)
                | (this.destination_chip_p & 31);
        message_data[4] = tmp;

        //Compose  Source_port+cpu = 3 MSBs as port and 5 LSBs as cpu
        tmp = ((this.source_port & 7) << 5) | (this.source_cpu & 31);
        message_data[5] = tmp;
        message_data[6] = this.destination_chip_y;
        message_data[7] = this.destination_chip_x;
        message_data[8] = this.source_chip_y;
        message_data[9] = this.source_chip_x;

        return message_data;
    }

    int length_in_bytes(){
        return this.length;
    }
}