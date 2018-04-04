
import java.net.DatagramPacket;
import java.util.concurrent.ConcurrentLinkedDeque;

/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */

/**
 *
 * @author alan
 */
public class ReaderThread extends Thread{
    
    private final UDPConnection connection;
    private final ConcurrentLinkedDeque<DatagramPacket> messqueue;

    public ReaderThread(UDPConnection connection, 
                        ConcurrentLinkedDeque<DatagramPacket> messqueue) {
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
            }

        } while (!connection.isClosed());
    }
}
