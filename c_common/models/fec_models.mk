MAKEFILE_PATH := $(abspath $(lastword $(MAKEFILE_LIST)))
CURRENT_DIR := $(dir $(MAKEFILE_PATH))
APP_OUTPUT_DIR := $(abspath $(CURRENT_DIR)../../spinn_front_end_common/common_model_binaries/)/

include $(CURRENT_DIR)../front_end_common_lib/local.mk

.PRECIOUS: $(MODIFIED_DIR)%.c $(LOG_DICT_FILE)
