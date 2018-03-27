INSTALL_DIRS = host_data_receiver
BUILD_DIRS = host_data_receiver

all: install build
	
build:
	@for d in $(BUILD_DIRS); do $(MAKE) -C $$d build || exit $$?; done

install:
	@for d in $(INSTALL_DIRS); do $(MAKE) -C $$d install || exit $$?; done

clean:
	@for d in $(BUILD_DIRS) $(INSTALL_DIRS); do $(MAKE) -C $$d clean || exit $$?; done
	@for d in $(INSTALL_DIRS); do $(MAKE) -C $$d install-clean || exit $$?; done

.PHONY: all build install clean
