# If SPINN_DIRS is not defined, this is an error!
ifndef SPINN_DIRS
    $(error SPINN_DIRS is not set.  Please define SPINN_DIRS (possibly by running "source setup" in the spinnaker package folder))
endif

CURRENT_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
SOURCE_DIR := $(abspath $(CURRENT_DIR))
ROOT_DIR := $(abspath $(CURRENT_DIR)../..)
SOURCE_DIRS += $(SOURCE_DIR)
APP_OUTPUT_DIR := $(abspath $(ROOT_DIR)/spinn_front_end_common/common_model_binaries/)/

include $(ROOT_DIR)/c_common/front_end_common_lib/FrontEndCommon.mk
