import static java.lang.Math.ceil;
import static java.lang.Math.min;
import static java.nio.ByteOrder.LITTLE_ENDIAN;

import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.PrintWriter;
import java.net.DatagramPacket;
import java.net.InetSocketAddress;
import java.net.SocketException;
import java.nio.ByteBuffer;
import java.util.BitSet;
import java.util.concurrent.LinkedBlockingDeque;
import java.util.concurrent.TimeUnit;
import java.util.logging.Level;
import java.util.logging.Logger;

public class HostDataReceiver extends Thread {
    public enum SCPCommands {
        SET_IPTAG(26);
        private short value;

        SCPCommands(int value) {
            this.value = (short) value;
        }

        public short getValue() {
            return value;
        }
    }

    // consts for data and converting between words and bytes
    private static final int DATA_PER_FULL_PACKET = 68;
    private static final int DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM = DATA_PER_FULL_PACKET
            - 1;
    private static final int BYTES_PER_WORD = 4;
    private static final int END_FLAG_SIZE_IN_BYTES = 4;
    private static final int SEQUENCE_NUMBER_SIZE = 4;
    private static final int LAST_MESSAGE_FLAG_BIT_MASK = 0x80000000;

    private static final int SDP_PACKET_START_SENDING_COMMAND_ID = 100;
    private static final int SDP_PACKET_START_MISSING_SEQ_COMMAND_ID = 1000;
    private static final int SDP_PACKET_MISSING_SEQ_COMMAND_ID = 1001;

    // time out constants
    public static final int TIMEOUT_RETRY_LIMIT = 20;
    private static final int TIMEOUT_PER_SENDING_IN_MILLISECONDS = 10;
    private static final int TIMEOUT_PER_RECEIVE_IN_MILLISECONDS = 1000;

    private final int port_connection;
    private final int placement_x;
    private final int placement_y;
    private final int placement_p;
    private final String hostname;
    private final int length_in_bytes;
    private final int memory_address;
    private final int chip_x;
    private final int chip_y;
    private final int iptag;
    private final LinkedBlockingDeque<DatagramPacket> messqueue;
    private final byte[] buffer;
    private final int max_seq_num;
    private boolean finished;
    private int miss_cnt;
    private BitSet received_seq_nums;

    Logger log = Logger.getLogger(ProcessorThread.class.getName());

    public HostDataReceiver(int port_connection, int placement_x,
            int placement_y, int placement_p, String hostname,
            int length_in_bytes, int memory_address, int chip_x, int chip_y,
            int iptag) {
        this.port_connection = port_connection;
        this.placement_x = placement_x;
        this.placement_y = placement_y;
        this.placement_p = placement_p;
        this.hostname = hostname;
        this.length_in_bytes = length_in_bytes;
        this.memory_address = memory_address;
        this.chip_x = chip_x;
        this.chip_y = chip_y;
        this.iptag = iptag;

        // allocate queue for messages
        messqueue = new LinkedBlockingDeque<>();

        buffer = new byte[length_in_bytes];

        max_seq_num = calculateMaxSeqNum(length_in_bytes);
        received_seq_nums = new BitSet(max_seq_num);

        finished = false;
        miss_cnt = 0;
    }

    /**
     * Divide one integer by another with rounding up.
     */
    private static final int ceildiv(int numerator, int denominator) {
        return (int) ceil((float) numerator / (float) denominator);
    }

    public byte[] get_data() throws InterruptedException {
        // create connection
        UDPConnection sender = null;
        try {
            sender = new UDPConnection(17893, hostname,
                    TIMEOUT_PER_RECEIVE_IN_MILLISECONDS);
        } catch (SocketException ex) {
            log.log(Level.SEVERE, "failed to create UDP connection", ex);
            return null;
        }

        // send the initial command to start data transmission
        sendInitialCommand(sender, sender);

        ReaderThread reader = new ReaderThread(sender);
        ProcessorThread processor = new ProcessorThread(sender);

        reader.start();
        processor.start();

        reader.join();
        processor.join();

        log.fine("done!!!");
        return buffer;
    }

    public void get_data_threadable(String filepath_read,
            String filepath_missing)
            throws FileNotFoundException, IOException, InterruptedException {
        try (FileOutputStream fp1 = new FileOutputStream(filepath_read);
                PrintWriter fp2 = new PrintWriter(filepath_missing)) {
            get_data();

            fp1.write(buffer);
            fp2.println(miss_cnt);
        }
    }

    private byte[] build_set_iptag_req(boolean strip_sdp,
            InetSocketAddress sock_address) {
        int seq = 0;
        int arg = 0;

        ByteBuffer byteBuffer = ByteBuffer.allocate(4 * 4);
        byteBuffer.order(LITTLE_ENDIAN);

        byteBuffer.putShort(SCPCommands.SET_IPTAG.getValue());
        byteBuffer.putShort((short) seq);

        arg = arg | (strip_sdp ? 1 << 28 : 0) | (1 << 16) | iptag;

        byteBuffer.putInt(arg);
        byteBuffer.putInt(sock_address.getPort());
        byteBuffer.put(sock_address.getAddress().getAddress());

        return byteBuffer.array();
    }

    public boolean retransmit_missing_sequences(UDPConnection sender,
            BitSet received_seq_nums) throws InterruptedException {

        int length_via_format2;
        int seq_num_offset;
        int length_left_in_packet;
        int size_of_data_left_to_transmit;
        boolean first;
        int n_packets;
        int i;

        // Calculate number of missing sequences based on difference between
        // expected and received
        int miss_dim = max_seq_num - received_seq_nums.cardinality();

        ByteBuffer missing_seq = ByteBuffer.allocate(miss_dim * 4);
        missing_seq.order(LITTLE_ENDIAN);
        int j = 0;

        // Calculate missing sequence numbers and add them to "missing"
        log.fine("max seq num of " + max_seq_num);
        for (i = 0; i < max_seq_num; i++) {
            if (!received_seq_nums.get(i)) {
                missing_seq.putInt(i);
                j++;
                miss_cnt++;
            }
        }
        missing_seq.rewind();

        if (log.isLoggable(Level.FINE)) {
            for (i = 0; i < miss_dim; i++) {
                log.fine("missing seq " + missing_seq.getInt());
            }
            missing_seq.rewind();
        }

        // Set correct number of lost sequences
        miss_dim = j;

        // No missing sequences
        if (miss_dim == 0) {
            return true;
        }

        n_packets = 1;
        length_via_format2 = miss_dim - (DATA_PER_FULL_PACKET - 2);

        if (length_via_format2 > 0) {
            n_packets += ceildiv(length_via_format2, DATA_PER_FULL_PACKET - 1);
        }

        // Transmit missing sequences as a new SDP Packet
        first = true;
        seq_num_offset = 0;

        for (i = 0; i < n_packets; i++) {
            ByteBuffer data = null;
            length_left_in_packet = DATA_PER_FULL_PACKET;

            // If first, add n packets to list; otherwise just add data
            if (first) {
                // Get left over space / data size
                size_of_data_left_to_transmit = min(length_left_in_packet - 2,
                        miss_dim - seq_num_offset);
                data = ByteBuffer.allocate(
                        size_of_data_left_to_transmit * BYTES_PER_WORD);
                data.order(LITTLE_ENDIAN);

                // Pack flag and n packets
                data.putInt(SDP_PACKET_START_MISSING_SEQ_COMMAND_ID);
                data.putInt(n_packets);

                // Update state
                length_left_in_packet -= 2;
                first = false;
            } else {
                // Get left over space / data size
                size_of_data_left_to_transmit = min(
                        DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM,
                        miss_dim - seq_num_offset);
                data = ByteBuffer.allocate(
                        size_of_data_left_to_transmit * BYTES_PER_WORD);
                data.order(LITTLE_ENDIAN);

                // Pack flag
                data.putInt(SDP_PACKET_MISSING_SEQ_COMMAND_ID);
                length_left_in_packet -= 1;
            }

            // System.out.println("a");
            for (int element = 0; element < size_of_data_left_to_transmit; element++) {
                data.putInt(missing_seq.getInt());
            }

            seq_num_offset += length_left_in_packet;

            sender.sendData(new SDPMessage(placement_x, placement_y,
                    placement_p, port_connection, SDPMessage.REPLY_NOT_EXPECTED,
                    255, 255, 255, 0, 0, data.array()));

            Thread.sleep(TIMEOUT_PER_SENDING_IN_MILLISECONDS);
        }

        return false;
    }

    public void process_data(UDPConnection sender, DatagramPacket packet)
            throws Exception {
        int first_packet_element;
        int offset;
        int true_data_length;
        int seq_num;
        boolean is_end_of_stream;

        ByteBuffer data = ByteBuffer.wrap(packet.getData(), 0,
                packet.getLength());
        data.order(LITTLE_ENDIAN);
        data.rewind();
        first_packet_element = data.getInt();

        seq_num = first_packet_element & ~LAST_MESSAGE_FLAG_BIT_MASK;
        is_end_of_stream = ((first_packet_element
                & LAST_MESSAGE_FLAG_BIT_MASK) != 0);

        if (seq_num > max_seq_num || seq_num < 0) {
            throw new IllegalStateException("Got insane sequence number");
        }

        offset = seq_num * DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM
                * BYTES_PER_WORD;

        true_data_length = (offset + packet.getLength() - SEQUENCE_NUMBER_SIZE);

        if (true_data_length > length_in_bytes) {
            throw new IllegalStateException(
                    "Receiving more data than expected");
        }

        if (is_end_of_stream && packet.getLength() == END_FLAG_SIZE_IN_BYTES) {
            // empty
        } else {
            System.arraycopy(packet.getData(), SEQUENCE_NUMBER_SIZE, buffer,
                    offset, true_data_length - offset);
        }

        try {
            received_seq_nums.set(seq_num);
        } catch (IndexOutOfBoundsException e) {
            // Should be unreachable
            throw new IllegalStateException(e);
        }

        if (is_end_of_stream) {
            if (!check()) {
                finished |= retransmit_missing_sequences(sender,
                        received_seq_nums);
            } else {
                finished = true;
            }
        }
    }

    private void sendInitialCommand(UDPConnection sender,
            UDPConnection receiver) {
        // Build an SCP request to set up the IP Tag associated to this socket
        byte[] scp_req = build_set_iptag_req(true,
                receiver.getLocalSocketAddress());

        // Send SCP request and get the reply back
        sender.sendData(new SDPMessage(chip_x, chip_y, 0, 0,
                SDPMessage.REPLY_EXPECTED, 255, 255, 255, 0, 0, scp_req));
        sender.receiveData(300); // TODO: Validate this reply

        // Create Data request SDP packet
        ByteBuffer byteBuffer = ByteBuffer.allocate(3 * 4);
        byteBuffer.order(LITTLE_ENDIAN);
        byteBuffer.putInt(SDP_PACKET_START_SENDING_COMMAND_ID);
        byteBuffer.putInt(memory_address);
        byteBuffer.putInt(length_in_bytes);

        // build and send SDP message
        sender.sendData(new SDPMessage(placement_x, placement_y, placement_p,
                port_connection, SDPMessage.REPLY_NOT_EXPECTED, 255, 255, 255,
                0, 0, byteBuffer.array()));
    }

    private static int calculateMaxSeqNum(int length) {
        return ceildiv(length,
                DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM * BYTES_PER_WORD);
    }

    private boolean check() throws Exception {
        int recvsize = received_seq_nums.length();

        if (recvsize > max_seq_num + 1) {
            throw new Exception("Received more data than expected");
        }
        return recvsize == max_seq_num + 1;
    }

    public static final String TIMEOUT_MESSAGE = "Failed to hear from the "
            + "machine. Please try removing firewalls.";

    private class ProcessorThread extends Thread {
        private final UDPConnection connection;
        private int timeoutcount = 0;

        public ProcessorThread(UDPConnection connection) {
            super("ProcessorThread");
            this.connection = connection;
        }

        private void processOnePacket() throws Exception {
            DatagramPacket p = messqueue.poll(1, TimeUnit.SECONDS);
            if (p != null) {
                process_data(connection, p);
            } else {
                timeoutcount++;
                if (timeoutcount > TIMEOUT_RETRY_LIMIT) {
                    log.severe(TIMEOUT_MESSAGE);
                    return;
                }
                if (!finished) {
                    // retransmit missing packets
                    log.fine("doing reinjection");
                    finished = retransmit_missing_sequences(connection,
                            received_seq_nums);
                }
            }
        }

        @Override
        public void run() {
            try {
                while (!finished) {
                    try {
                        processOnePacket();
                    } catch (InterruptedException e) {
                        // Do nothing
                    }
                }
            } catch (Exception ex) {
                log.log(Level.SEVERE, "problem in packet processing thread",
                        ex);
            } finally {
                // close socket and inform the reader that transmission is
                // completed
                connection.close();
            }
            finished = true;
        }
    }

    private class ReaderThread extends Thread {
        private final UDPConnection connection;

        public ReaderThread(UDPConnection connection) {
            super("ReadThread");
            this.connection = connection;
        }

        @Override
        public void run() {
            // While socket is open add messages to the queue
            do {
                DatagramPacket recvd = connection.receiveData(400);

                if (recvd != null) {
                    messqueue.push(recvd);
                    log.fine("pushed");
                }
            } while (!connection.isClosed());
        }
    }
}
