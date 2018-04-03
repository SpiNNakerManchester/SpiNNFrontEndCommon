import java.io.IOException;
import java.net.DatagramSocket;
import java.net.DatagramPacket;
import java.net.InetSocketAddress;
import java.net.SocketException;

public class UDPConnection{

    private DatagramSocket sock;
    private boolean can_send;
    private InetSocketAddress local_ip_address = null;
    private InetSocketAddress remote_ip_address;

    public UDPConnection(
            int local_port,
            String local_host,
            int remote_port,
            String remote_host) throws SocketException{
        this.can_send = false;
        this.remote_ip_address = new InetSocketAddress(remote_host, remote_port);
        this.sock = new DatagramSocket();

        if (!local_host.equals("")) {
            this.local_ip_address = new InetSocketAddress(local_host, local_port);
            this.sock.bind(this.local_ip_address);
        }
    }
    
    boolean is_closed(){
        return this.sock.isClosed();
    }

    DatagramPacket receive_data(byte[] data, int length){
        DatagramPacket packet = new DatagramPacket(data, length);
        try{
            sock.receive(packet);
            return packet;
        } catch(IOException e){
            System.out.println("failed to recieve packet");
            return null;
        }      
    }

    void send_data(byte[] data, int length){
        DatagramPacket packet = new DatagramPacket(
                data, length, this.remote_ip_address);
        try{
            sock.send(packet);
        } catch(IOException e){
            System.out.printf("failed to send packet due to %s\n", e.toString());
        }
    }

    void close(){
        sock.close();
    }

    int get_local_port() {
        return this.sock.getLocalPort();
    }

    InetSocketAddress get_local_ip(){
        if (this.local_ip_address == null){
            return (InetSocketAddress) this.sock.getLocalSocketAddress();
        }
        return this.local_ip_address;
    }
}