
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.logging.Level;
import java.util.logging.Logger;

public class Main2 {

    public final static int N_ARGS = 12;
    public final int IP_ADDRESS_SIZE = 24;
    public final int FILE_PATH_SIZE = 1024;

    public enum ArgPlacements {
        PLACEMENT_X_POSITION(2),
        PLACEMENT_Y_POSITION(3),
        PLACEMENT_P_POSITION(4),
        PORT_NUMBER_POSITION(1),
        HOSTNAME_POSITION(0),
        FILE_PATH_READ_POSITION(5),
        FILE_PATH_MISS_POSITION(6),
        LENGTH_IN_BYTES(7),
        MEMORY_ADDRESS(8),
        CHIP_X(9),
        CHIP_Y(10),
        IPTAG(11);
                
        private int value;
        private ArgPlacements(int value){
            this.value = value;}
        
        public int value(){
            return this.value;
        }
    };

    public static void main(String[] args) {
        // variables
        
        int placement_x = 0;
        int placement_y = 0;
        int placement_p = 0;
        int port_connection = 0;
        int length_in_bytes = 0;
        int memory_address = 0;
        String hostname = "";
        String file_pathr = "";
        String file_pathm = "";
        //FILE * stored_data;
        String output = "";
        String buffer;
        int chip_x = 0;
        int chip_y = 0;
        int iptag = 0;
        
        if (args.length != 12){
            System.out.println("not the correct number of parameters");
            System.out.printf(" got %d args instead", args.length);
        }
        else{
            // get arguments
            hostname = args[ArgPlacements.HOSTNAME_POSITION.value()];
            placement_x = Integer.parseInt(args[ArgPlacements.PLACEMENT_X_POSITION.value()]);
            placement_y = Integer.parseInt(args[ArgPlacements.PLACEMENT_Y_POSITION.value()]);
            placement_p = Integer.parseInt(args[ArgPlacements.PLACEMENT_P_POSITION.value()]);
            port_connection = Integer.parseInt(args[ArgPlacements.PORT_NUMBER_POSITION.value()]);
            length_in_bytes = Integer.parseInt(args[ArgPlacements.LENGTH_IN_BYTES.value()]);
            memory_address = Integer.parseInt(args[ArgPlacements.MEMORY_ADDRESS.value()]);
            file_pathr = args[ArgPlacements.FILE_PATH_READ_POSITION.value()];
            file_pathm = args[ArgPlacements.FILE_PATH_MISS_POSITION.value()];
            chip_x = Integer.parseInt(args[ArgPlacements.CHIP_X.value()]);
            chip_y = Integer.parseInt(args[ArgPlacements.CHIP_Y.value()]);
            iptag = Integer.parseInt(args[ArgPlacements.IPTAG.value()]);

            HostDataReceiver collector = new HostDataReceiver(
                    port_connection, placement_x, placement_y,
                    placement_p, hostname, length_in_bytes, memory_address,
                    chip_x, chip_y, iptag);
            try {
                collector.get_data_threadable(file_pathr, file_pathm);
            } catch (IOException | InterruptedException ex) {
                Logger.getLogger(Main2.class.getName()).log(Level.SEVERE, null, ex);
            }

        }
    }
}