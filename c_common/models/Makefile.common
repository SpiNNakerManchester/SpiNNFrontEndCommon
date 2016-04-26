# If SPINN_DIRS is not defined, this is an error!
ifndef SPINN_DIRS
    $(error SPINN_DIRS is not set.  Please define SPINN_DIRS (possibly by running "source setup" in the spinnaker package folder))
endif

MAKEFILE_PATH := $(abspath $(lastword $(MAKEFILE_LIST)))
CURRENT_DIR := $(dir $(MAKEFILE_PATH))
SOURCE_DIR := $(abspath $(CURRENT_DIR))
SOURCE_DIRS += $(SOURCE_DIR)
APP_OUTPUT_DIR := $(abspath $(CURRENT_DIR)../../spinn_front_end_common/common_model_binaries/)/

include $(CURRENT_DIR)../front_end_common_lib/Makefile.SpiNNFrontEndCommon
