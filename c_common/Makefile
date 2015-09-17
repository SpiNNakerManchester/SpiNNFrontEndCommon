INSTALL_DIRS = front_end_common_lib
BUILD_DIRS = models

all: install build
	
build: install $(BUILD_DIRS)
	for d in $(BUILD_DIRS); do (cd $$d; "$(MAKE)") || exit $$?; done

install: $(INSTALL_DIRS)
	for d in $(INSTALL_DIRS); do (cd $$d; "$(MAKE)" install) || exit $$?; done

clean: $(BUILD_DIRS)
	for d in $(BUILD_DIRS) $(INSTALL_DIRS); do (cd $$d; "$(MAKE)" clean) || exit $$?; done
	for d in $(INSTALL_DIRS); do (cd $$d; "$(MAKE)" install-clean) || exit $$?; done
