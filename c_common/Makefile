INSTALL_DIRS = front_end_common_lib
BUILD_DIRS = models

all: install build
	
build: install $(BUILD_DIRS)
	@for d in $(BUILD_DIRS); do $(MAKE) -C $$d || exit $$?; done

install: $(INSTALL_DIRS)
	@for d in $(INSTALL_DIRS); do $(MAKE) -C $$d install || exit $$?; done

clean: $(BUILD_DIRS)
	@for d in $(BUILD_DIRS) $(INSTALL_DIRS); do $(MAKE) -C $$d clean || exit $$?; done
	@for d in $(INSTALL_DIRS); do $(MAKE) -C $$d install-clean || exit $$?; done

.PHONY: all build install clean
