
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
                        ConcurrentLinkedDeque<DatagramPacket> messqueue){
        this.connection = connection;
        this.messqueue = messqueue;
        this.setName("ReadThread");
    }
    
    @Override
    public void run(){
        byte [] data = new byte[400];

        // While socket is open add messages to the queue
        do {
            DatagramPacket recvd = this.connection.receiveData(data, 400);

            if (recvd != null){
                this.messqueue.push(recvd);
            }

        } while (!this.connection.isClosed());
    }
}
