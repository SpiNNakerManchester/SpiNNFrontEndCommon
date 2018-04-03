import java.io.IOException;
import java.net.DatagramSocket;
import java.net.DatagramPacket;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.SocketAddress;
import java.net.SocketException;

public class UDPConnection implements AutoCloseable {
    private DatagramSocket sock;
    private InetSocketAddress remote_ip_address;

    // Simple passthrough constructors that allow sensible defaults
    public UDPConnection(
            int remote_port,
            String remote_host) throws SocketException {
    	this(0, null, remote_port, remote_host);
    }
    public UDPConnection(
    	    String local_host, int remote_port, String remote_host) 
            throws SocketException {
    	this(0, local_host, remote_port, remote_host);
    }
    public UDPConnection(
            int local_port, int remote_port, String remote_host) 
            throws SocketException {
    	this(local_port, null, remote_port, remote_host);
    }

    // The real constructor
    public UDPConnection(
            int local_port, String local_host, int remote_port, 
            String remote_host) 
            throws SocketException {
        this.remote_ip_address = new InetSocketAddress(remote_host, remote_port);
        if (local_host == null || local_host.isEmpty()) {
            this.sock = new DatagramSocket();
        } else {
            System.out.println("A");
            this.sock = new DatagramSocket(
                new InetSocketAddress(local_host, local_port));
        }
        this.sock.setSoTimeout(500);
    }
    
    public boolean is_closed() {
        return this.sock.isClosed();
    }

    public DatagramPacket receive_data(byte[] data, int length) {
        DatagramPacket packet = new DatagramPacket(data, length);
        try {
            sock.receive(packet);
            return packet;
        } catch(IOException e) {
            System.out.println("failed to recieve packet");
            return null;
        }      
    }

    public void send_data(byte[] data, int length) {
        DatagramPacket packet = new DatagramPacket(
                data, length, this.remote_ip_address);
        try {
            sock.send(packet);
        } catch(IOException e) {
            System.out.printf("failed to send packet due to %s\n", e.toString());
        }
    }

    @Override
    public void close() {
        sock.close();
    }

    public int get_local_port() {
        return this.sock.getLocalPort();
    }

    public InetSocketAddress get_local_ip() {
    	return (InetSocketAddress) this.sock.getLocalSocketAddress();
    }
}
