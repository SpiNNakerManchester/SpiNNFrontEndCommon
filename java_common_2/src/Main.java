
import java.io.IOException;
import java.util.logging.Level;
import java.util.logging.Logger;

public class Main {

    public final int N_ARGS = 13;
    public final int IP_ADDRESS_SIZE = 24;
    public final int FILE_PATH_SIZE = 1024;

    public enum ArgPlacements {
        PLACEMENT_X_POSITION(3),
        PLACEMENT_Y_POSITION(4),
        PLACEMENT_P_POSITION(5),
        PORT_NUMBER_POSITION(2),
        HOSTNAME_POSITION(1),
        FILE_PATH_READ_POSITION(6),
        FILE_PATH_MISS_POSITION(7),
        LENGTH_IN_BYTES(8),
        MEMORY_ADDRESS(9),
        CHIP_X(10),
        CHIP_Y(11),
        IPTAG(12);
                
        private int value;
        private ArgPlacements(int value){
            this.value = value;}
        
        public int value(){
            return this.value;
        }
    };

    static void main(String[] args) {
        // variables
        
        int i;
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
        
        if (args.length != 13){
            System.out.println("not the correct number of parameters");
        }
        else{
            // get arguments
            placement_x = Integer.parseInt(args[ArgPlacements.PLACEMENT_X_POSITION.value()]);
            placement_y = Integer.parseInt(args[ArgPlacements.PLACEMENT_Y_POSITION.value()]);
            placement_p = Integer.parseInt(args[ArgPlacements.PLACEMENT_P_POSITION.value()]);
            port_connection = Integer.parseInt(args[ArgPlacements.PORT_NUMBER_POSITION.value()]);
            length_in_bytes = Integer.parseInt(args[ArgPlacements.LENGTH_IN_BYTES.value()]);
            memory_address = Integer.parseInt(args[ArgPlacements.MEMORY_ADDRESS.value()]);
            hostname = args[ArgPlacements.HOSTNAME_POSITION.value()];
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
            } catch (IOException ex) {
                System.out.println(ex);
            }

        }
    }
}