
import java.net.DatagramPacket;
import java.util.BitSet;
import java.util.NoSuchElementException;
import java.util.concurrent.ConcurrentLinkedDeque;
import java.util.logging.Level;
import java.util.logging.Logger;

public class ProcessorThread extends Thread{
    
    private final UDPConnection connection;
    private final ConcurrentLinkedDeque<DatagramPacket> messqueue;
    private final HostDataReceiver parent;
    private Boolean finished;
    private final BitSet received_seq_nums;
    
    public ProcessorThread(UDPConnection connection, 
                           ConcurrentLinkedDeque<DatagramPacket> messqueue,
                           HostDataReceiver parent, Boolean finished,
                           BitSet received_seq_nums){
        this.connection = connection;
        this.messqueue = messqueue;
        this.parent = parent;
        this.finished = finished; 
        this.received_seq_nums = received_seq_nums;
        this.setName("ProcessorThread");
    }
            
            
    
    @Override
    public void run(){
        int timeoutcount = 0;
        
        while (!this.finished) {
            try {
                DatagramPacket p = this.messqueue.pop();
                
                this.finished = this.parent.process_data(
                        this.connection, this.finished, 
                        this.received_seq_nums, p);
            } catch (NoSuchElementException e) {
                if (timeoutcount > this.parent.TIMEOUT_RETRY_LIMIT) {
                    System.out.println(
                        "ERROR: Failed to hear from the machine. "
                        + "Please try removing firewalls");
                    this.connection.close();
                    return;
                }

                timeoutcount++;

                if (!this.finished) {
                    try {
                        // retransmit missing packets
                        this.finished = 
                            this.parent.retransmit_missing_sequences(
                                this.connection, this.received_seq_nums);
                    } catch (InterruptedException ex) {
                        Logger.getLogger(ProcessorThread.class.getName()).log(
                            Level.SEVERE, null, ex);
                    }
                }
            } catch (Exception ex) {
                Logger.getLogger(ProcessorThread.class.getName()).log(
                    Level.SEVERE, null, ex);
            }
        }
        
        // close socket and inform the reader that transmission is completed
        this.connection.close();
        this.finished = true;
    }
}
