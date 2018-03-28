INSTALL_DIRS = host_data_receiver
BUILD_DIRS = host_data_receiver

all: install build
	
build: common/libcommon.a
	@for d in $(BUILD_DIRS); do $(MAKE) -C $$d build || exit $$?; done

common/libcommon.a:
	$(MAKE) -C common libcommon.a

install: build
	@for d in $(INSTALL_DIRS); do $(MAKE) -C $$d install || exit $$?; done

clean:
	@$(MAKE) -C common clean
	@for d in $(BUILD_DIRS) $(INSTALL_DIRS); do $(MAKE) -C $$d clean || exit $$?; done
	@for d in $(INSTALL_DIRS); do $(MAKE) -C $$d install-clean || exit $$?; done

.PHONY: all build install clean
