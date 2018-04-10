
import java.net.DatagramPacket;
import java.util.BitSet;
import java.util.concurrent.LinkedBlockingDeque;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.concurrent.TimeUnit;

public class ProcessorThread extends Thread {
    private final UDPConnection connection;
    private final LinkedBlockingDeque<DatagramPacket> messqueue;
    private final HostDataReceiver parent;
    private boolean finished;
    private final BitSet received_seq_nums;

    public static final String TIMEOUT_MESSAGE = 
        "ERROR: " + 
        "Failed to hear from the machine. Please try removing firewalls.";

    public ProcessorThread(
            UDPConnection connection,
            LinkedBlockingDeque<DatagramPacket> messqueue,
            HostDataReceiver parent, boolean finished,
            BitSet received_seq_nums) {
        super("ProcessorThread");
        this.connection = connection;
        this.messqueue = messqueue;
        this.parent = parent;
        this.finished = finished;
        this.received_seq_nums = received_seq_nums;
    }

    @Override
    public void run() {
        int timeoutcount = 0;
        Logger log = Logger.getLogger(ProcessorThread.class.getName());

        try {
            while (!finished) {
                try {
                    DatagramPacket p = messqueue.poll(
                        1, TimeUnit.SECONDS);
                    if(p != null){
                        finished = parent.process_data(connection, finished,
                                                       received_seq_nums, p);
                    }
                    else{
                        timeoutcount++;
                        if (timeoutcount > 
                                HostDataReceiver.TIMEOUT_RETRY_LIMIT) {
                            System.out.println(TIMEOUT_MESSAGE);
                            return;
                        }
                        if (!finished) {
                            // retransmit missing packets
                            //System.out.println("doing reinjection");
                            finished = parent.retransmit_missing_sequences(
                                connection, received_seq_nums);
                        }
                    }
                } 
                catch (InterruptedException e) {}
            }
        } catch (Exception ex) {
            log.log(Level.SEVERE, "problem in packet processing thread", ex);
        } finally {
            // close socket and inform the reader that transmission is completed
            connection.close();
        }
        finished = true;
    }

    public boolean isFinished() {
        return finished;
    }
}
