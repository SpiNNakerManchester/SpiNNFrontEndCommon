BUILD_DIRS = compressor_bit_field_models \
	         live_packet_gather \
	         chip_power_monitor \
	         data_speed_up_packet_gatherer \
	         extra_monitor_support

all: $(BUILD_DIRS)
	@for d in $(BUILD_DIRS); do $(MAKE) -C $$d || exit $$?; done

clean: $(BUILD_DIRS)
	@for d in $(BUILD_DIRS); do $(MAKE) -C $$d clean || exit $$?; done
