import java.net.DatagramSocket;
import java.net.DatagramPacket;
import java.net.SocketAddress;
import java.net.InetSocketAddress;

public class UDPConnection{

    private DatagramSocket sock;
    private boolean can_send;
    private SocketAddress local_ip_address;
    private SocketAddress remote_ip_address;

    public UDPConnection(
            int local_port,
            String local_host,
            int remote_port,
            String remote_host){
        this.can_send = false;
        this.remote_ip_address = new InetSocketAddress(remote_host, remote_port);
        this.sock = new DatagramSocket();
        if (local_host != null) {
            this.local_ip_address = new InetSocketAddress(local_host, local_port);
            this.sock.bind(this.local_ip_address);
        }
    }

    int receive_data(byte[] data, int length){
        DatagramPacket packet = new DatagramPacket(data, length);
        sock.receive(packet);
        return packet.getLength();
    }

    void send_data(byte[] data, int length){
        DatagramPacket packet = new DatagramPacket(data, length, this.remote_ip_address);
        sock.send(packet);
    }

    void close(){
        sock.close();
    }

    int get_local_port() {
        return this.local_port;
    }

    SocketAddress get_local_ip(){
        return this.local_ip_address
    }
}