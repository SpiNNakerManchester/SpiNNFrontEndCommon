# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# SPINN_DIRS must be set for this file to be found

# APP_OUTPUT_DIR directory to save a and dict files to (none installed)
# APP_OUTPUT_DIR must end with /
ifndef APP_OUTPUT_DIR
    $(error APP_OUTPUT_DIR is not set.  Please define APP_OUTPUT_DIR)
endif
APP_OUTPUT_DIR :=  $(abspath $(APP_OUTPUT_DIR))/

# APP name for a and dict files
ifndef APP
    $(error APP is not set.  Please define APP)
endif

# BUILD_DIR local directory to put o files into
ifndef BUILD_DIR
    BUILD_DIR := build/
endif
BUILD_DIR := $(abspath $(BUILD_DIR))/

# SOURCE_DIRS space-separated list of directories where the raw c and h files
# are
ifndef SOURCE_DIRS
    SOURCE_DIRS := src/
endif
SOURCE_DIRS := $(patsubst %, %/, $(abspath $(SOURCE_DIRS)))

# SOURCES one or more unmodified c files to build
# Each source in SOURCES MUST be relative to one of the directories in
# SOURCE_DIRS; it MUST NOT include the full path
ifndef SOURCES
    $(error SOURCES is not set.  Please define SOURCES)
endif

# Define a macro to be run for every source directory
# The chain of operation of compilation for each source directory is:
# 1. Convert c and h files from original source directory to modified source
#    directory, translating the log messages as you go, and generate the log
#    dictionary.
# 2. Build the object file from the modified source files.
# Note that the rules for c / h / dict are all the same - the whole set of 
# sources is copied only once after which all the targets are now available
define add_source_dir#(src_dir, modified_dir)

$(2): $(1)
	python -m spinn_utilities.make_tools.converter $(1) $(2) $(DATABASE_ID) $(APP_OUTPUT_DIR)/logs.sqlite3

$(2)%.c: $(1)%.c
	python -m spinn_utilities.make_tools.converter $(1) $(2) $(DATABASE_ID) $(APP_OUTPUT_DIR)/logs.sqlite3

$(2)%.h: $(1)%.h
	python -m spinn_utilities.make_tools.converter $(1) $(2) $(DATABASE_ID) $(APP_OUTPUT_DIR)/logs.sqlite3

# Build the o files from the modified sources
$$(BUILD_DIR)%.o: $(2)%.c
	# local
	-@mkdir -p $$(dir $$@)
	$$(CC) $$(CFLAGS) -o $$@ $$<
endef

define modified_dir#(src_dir)
    $(dir $(abspath $(1)))modified_src/
endef

# Add the default libraries and options
LIBRARIES += -lspinn_frontend_common -lspinn_common -lm
ifndef FEC_DEBUG
	FEC_DEBUG := PRODUCTION_CODE
endif
ifndef PROFILER
	PROFILER := PROFILER_DISABLED
endif

# Set up the default C Flags
ifndef FEC_OPT
    FEC_OPT = $(OTIME)
endif

CFLAGS += -Wall -Wextra -Wold-style-definition -D$(FEC_DEBUG) -D$(PROFILER) $(FEC_OPT)

# Get the application name hash by running md5sum on application name and 
# extracting the first 8 bytes
SHELL = bash
APPLICATION_NAME_HASH = $(shell echo -n "$(APP)" | (md5sum 2>/dev/null || md5) | cut -c 1-8)
CFLAGS += -DAPPLICATION_NAME_HASH=0x$(APPLICATION_NAME_HASH)

# Add the modified directories to the include path
CFLAGS += $(foreach d, $(sort $(SOURCE_DIRS)), -I $(call modified_dir,$(d)))

# default rule based on list ALL_TARGETS so more main targets can be added later
ALL_TARGETS += $(APP_OUTPUT_DIR)$(APP).aplx

$(foreach d, $(sort $(SOURCE_DIRS)), \
    $(eval ALL_MODIFIES_DIRS += $(call modified_dir, $(d))))

ALL_TARGETS += $(APP_OUTPUT_DIR)$(APP).aplx
all: $(ALL_MODIFIES_DIRS) $(ALL_TARGETS)

# Convert the objs into the correct format and set up the build rules
# Steps are:
# 1. Convert ?.c -> BUILD_DIR/?.o
# 2. For each unique (hence sort) source directory add the source directory
#    rules
_OBJS := $(SOURCES)
$(eval _OBJS := $(_OBJS:%.c=$(BUILD_DIR)%.o))
$(foreach d, $(sort $(SOURCE_DIRS)), \
    $(eval $(call add_source_dir, $(d), $(call modified_dir, $(d)))))
OBJECTS += $(_OBJS)

include $(SPINN_DIRS)/make/spinnaker_tools.mk

# Tidy and cleaning dependencies
clean:
	$(RM) $(TEMP_FILES) $(OBJECTS) $(BUILD_DIR)$(APP).elf $(BUILD_DIR)$(APP).txt $(ALL_TARGETS) $(BUILD_DIR)$(APP).nm $(BUILD_DIR)$(APP).elf $(BUILD_DIR)$(APP).bin
	rm -rf $(foreach d, $(sort $(SOURCE_DIRS)), $(call modified_dir, $(d)))

