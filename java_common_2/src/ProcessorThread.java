
import java.net.DatagramPacket;
import java.util.BitSet;
import java.util.NoSuchElementException;
import java.util.concurrent.ConcurrentLinkedDeque;
import java.util.logging.Level;
import java.util.logging.Logger;

public class ProcessorThread extends Thread {
	private final UDPConnection connection;
	private final ConcurrentLinkedDeque<DatagramPacket> messqueue;
	private final HostDataReceiver parent;
	private boolean finished;
	private final BitSet received_seq_nums;

	public static final String TIMEOUT_MESSAGE = "ERROR: "
			+ "Failed to hear from the machine. Please try removing firewalls.";

	public ProcessorThread(UDPConnection connection,
			ConcurrentLinkedDeque<DatagramPacket> messqueue,
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
					DatagramPacket p = messqueue.pop();

					finished = parent.process_data(connection, finished,
							received_seq_nums, p);
				} catch (NoSuchElementException e) {
					if (timeoutcount > HostDataReceiver.TIMEOUT_RETRY_LIMIT) {
						System.out.println(TIMEOUT_MESSAGE);
						return;
					}

					timeoutcount++;

					if (!finished) {
						// retransmit missing packets
						finished = parent.retransmit_missing_sequences(
								connection, received_seq_nums);
					}
				}
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
