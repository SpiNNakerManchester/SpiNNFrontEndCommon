
import java.net.DatagramPacket;
import java.util.concurrent.LinkedBlockingDeque;

/**
 *
 * @author alan
 */
public class ReaderThread extends Thread{
    
    private final UDPConnection connection;
    private final LinkedBlockingDeque<DatagramPacket> messqueue;

    public ReaderThread(UDPConnection connection, 
                        LinkedBlockingDeque<DatagramPacket> messqueue) {
    	super("ReadThread");
        this.connection = connection;
        this.messqueue = messqueue;
    }
    
    @Override
    public void run() {
        // While socket is open add messages to the queue
        do {
            DatagramPacket recvd = connection.receiveData(400);
            
            if (recvd != null) {
                messqueue.push(recvd);
                //System.out.println("pushed");
            }

        } while (!connection.isClosed());
    }
}
