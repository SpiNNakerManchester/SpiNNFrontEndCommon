import java.io.IOException;
import java.util.logging.Level;
import java.util.logging.Logger;
import static java.lang.Integer.parseInt;
import static java.lang.Integer.parseInt;

public class DataOutMainEntrance {

    public final static int N_ARGS = 12;
    public final int IP_ADDRESS_SIZE = 24;
    public final int FILE_PATH_SIZE = 1024;

    public enum Arg {
        /** The hostname */
        HOSTNAME(0),
        /** The port number */
        PORT_NUMBER(1),
        /** The X coord of the CPU to read from */
        PLACEMENT_X(2),
        /** The Y coord of the CPU to read from */
        PLACEMENT_Y(3),
        /** The P coord of the CPU to read from */
        PLACEMENT_P(4),
        /** Where to write data to */
        DATA_FILE(5),
        /** Where to report missing sequence numbers */
        MISSING_SEQS_FILE(6),
        /** How many bytes to read */
        LENGTH_IN_BYTES(7),
        /** Where to read from */
        MEMORY_ADDRESS(8),
        /** X coord for IPtag setting */
        CHIP_X(9),
        /** Y coord for IPtag setting */
        CHIP_Y(10),
        /** The ID of the IPtag */
        IPTAG(11);

        private final int value;

        private Arg(int value) {
            this.value = value;
        }

        public int value() {
            return this.value;
        }
    };

    private static Logger log = Logger.getLogger(
        DataOutMainEntrance.class.getName());

    public static void main(String[] args) {

        long startTime = System.nanoTime();
        if (args.length != 12) {
            System.err.println("not the correct number of parameters");
            System.err.printf(" got %d args instead", args.length);
            System.exit(1);
        }

        // variables
        int placement_x;
        int placement_y;
        int placement_p;
        int port_connection;
        int length_in_bytes;
        int memory_address;
        String hostname;
        String file_pathr;
        String file_pathm;
        int chip_x;
        int chip_y;
        int iptag;

        // log.info("got args " + java.util.Arrays.asList(args));

        // get arguments
        hostname = args[Arg.HOSTNAME.value()];
        placement_x = parseInt(args[Arg.PLACEMENT_X.value()]);
        placement_y = parseInt(args[Arg.PLACEMENT_Y.value()]);
        placement_p = parseInt(args[Arg.PLACEMENT_P.value()]);
        port_connection = parseInt(args[Arg.PORT_NUMBER.value()]);
        length_in_bytes = parseInt(args[Arg.LENGTH_IN_BYTES.value()]);
        memory_address = parseInt(args[Arg.MEMORY_ADDRESS.value()]);
        file_pathr = args[Arg.DATA_FILE.value()];
        file_pathm = args[Arg.MISSING_SEQS_FILE.value()];
        chip_x = parseInt(args[Arg.CHIP_X.value()]);
        chip_y = parseInt(args[Arg.CHIP_Y.value()]);
        iptag = parseInt(args[Arg.IPTAG.value()]);

        HostDataReceiver collector = new HostDataReceiver(port_connection,
                placement_x, placement_y, placement_p, hostname,
                length_in_bytes, memory_address, chip_x, chip_y, iptag);
        try {
            collector.get_data_threadable(file_pathr, file_pathm);
        } catch (IOException | InterruptedException ex) {
            log.log(Level.SEVERE, "failure retrieving data", ex);
        }

        long estimatedTime = System.nanoTime() - startTime;
        double seconds = (double)estimatedTime / 1000000000.0;
        System.out.println(
            "time taken to extract 20 MB just java is" + seconds + "MBS of " 
            + (((length_in_bytes) /1024 / 1024) * 8) / seconds);
    }
}