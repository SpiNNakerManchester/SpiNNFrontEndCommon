MAKEFILE_PATH := $(abspath $(lastword $(MAKEFILE_LIST)))
CURRENT_DIR := $(dir $(MAKEFILE_PATH))
APP_OUTPUT_DIR := $(abspath $(CURRENT_DIR)../../spinn_front_end_common/common_model_binaries/)/

include $(SPINN_DIRS)/make/local.mk

.PRECIOUS: $(MODIFIED_DIR)%.c $(LOG_DICT_FILE) $(BUILD_DIR)%.nm $(BUILD_DIR)%.elf $(BUILD_DIR)%.bin
