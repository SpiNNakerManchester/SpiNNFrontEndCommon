INSTALL_DIR = front_end_common_lib
BUILD_DIR = models
MODIFIED_INSTALL_DIR = modified_front_end_common_lib
MODIFIED_BUILD_DIR = modified_models

all: install build

build: install $(BUILD_DIR)
	# If spinn_utilities.make_tools.convertor not found please run setup.py for at least spinn_utilies
	python -m spinn_utilities.make_tools.convertor $(abspath $(BUILD_DIR)) $(abspath $(MODIFIED_BUILD_DIR)) 1000 || exit $$?; done
	@for d in $(MODIFIED_BUILD_DIR); do $(MAKE) -C $$d || exit $$?; done

install: $(INSTALL_DIR)
	# If spinn_utilities.make_tools.convertor not found please run setup.py for at least spinn_utilies
	python -m spinn_utilities.make_tools.convertor $(abspath $(INSTALL_DIR)) $(abspath $(MODIFIED_INSTALL_DIR)) 2000 || exit $$?; done
	@for d in $(MODIFIED_INSTALL_DIR); do $(MAKE) -C $$d install || exit $$?; done

clean: $(BUILD_DIRS)
	@for d in $(BUILD_DIR) $(INSTALL_DIR); do $(MAKE) -C $$d clean || exit $$?; done
	@for d in $(INSTALL_DIR); do $(MAKE) -C $$d install-clean || exit $$?; done
	rm -r $(abspath $(MODIFIED_INSTALL_DIR)) || true
	rm -r $(abspath $(MODIFIED_BUILD_DIR)) || true

convert:
	rm -r $(abspath $(MODIFIED_INSTALL_DIR)) || true
	rm -r $(abspath $(MODIFIED_BUILD_DIR)) || true
	# If spinn_utilities.make_tools.convertor not found please run setup.py for at least spinn_utilies
	python -m spinn_utilities.make_tools.convertor $(abspath $(BUILD_DIR)) $(abspath $(MODIFIED_BUILD_DIR)) 1000 || exit $$?; done
	python -m spinn_utilities.make_tools.convertor $(abspath $(INSTALL_DIR)) $(abspath $(MODIFIED_INSTALL_DIR)) 2000 || exit $$?; done

.PHONY: all build install clean
