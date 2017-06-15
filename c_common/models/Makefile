BUILD_DIRS = command_sender_multicast_source reverse_iptag_multicast_source live_packet_gather

all: $(BUILD_DIRS)
	@for d in $(BUILD_DIRS); do $(MAKE) -C $$d || exit $$?; done

clean: $(BUILD_DIRS)
	@for d in $(BUILD_DIRS); do $(MAKE) -C $$d clean || exit $$?; done
