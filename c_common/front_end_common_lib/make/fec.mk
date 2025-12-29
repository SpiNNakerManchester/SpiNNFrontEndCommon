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

# Find out where we are installed now (in the make subdirectory, so go up one)
FEC_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../)

# APP_OUTPUT_DIR directory to save a and dict files to (none installed)
# APP_OUTPUT_DIR must end with /
ifndef APP_OUTPUT_DIR
    $(error APP_OUTPUT_DIR is not set.  Please define APP_OUTPUT_DIR)
endif
APP_OUTPUT_DIR :=  $(abspath $(APP_OUTPUT_DIR))/

ifndef DATABASE_KEY
    # Makes in https://github.com/orgs/SpiNNakerManchester should user Upper case letters
    # So each user APP_OUTPUT_DIR should have a unique lower case one to avoid clashes
    $(error DATABASE_KEY is not set. Please set it to a unique lower case letter)
endif

# APP name for a files
ifndef APP
    $(error APP is not set.  Please define APP)
endif

# BUILD_DIR local directory to put o files into
ifndef BUILD_DIR
    BUILD_DIR := build/
endif
BUILD_DIR := $(abspath $(BUILD_DIR))/

# SOURCE_DIRS space-separated list of colon separated source and modified source
# directories where the raw c and h files are and the modified files are to be
# placed
ifndef SOURCE_DIRS
    SOURCE_DIRS := src/:$(BUILD_DIR)/modified_src/
endif

# SOURCES one or more unmodified c files to build
# Each source in SOURCES MUST be relative to one of the directories in
# SOURCE_DIRS; it MUST NOT include the full path
ifndef SOURCES
    $(error SOURCES is not set.  Please define SOURCES)
endif

# Get one of the paths from the colon separated pair in SOURCE_DIRS
# $1 = colon separated pair
# $2 = 1 for original source dir, 2 for modified source dir
get_path = $(abspath $(word $2, $(subst :, ,$1)))/

# Define a macro to be run for every source directory
# The chain of operation of compilation for each source directory is:
# 1. Convert c and h files from original source directory to modified source
#    directory, translating the log messages as you go, and generate the log
#    dictionary.
# 2. Build the object file from the modified source files.
# Note that the rules for c / h / dict are all the same - the whole set of
# sources is copied only once after which all the targets are now available.
# The argument src_dir is a colon separated source directory and modified source
# directory pair
define add_source_dir#(src_dir)
$(call get_path,$(1),2): $(wildcard $(call get_path,$(1),1)/**/*)
	python -m spinn_utilities.make_tools.converter $(call get_path,$(1),1) $(call get_path,$(1),2) $(APP_OUTPUT_DIR) $(DATABASE_KEY)

$(call get_path,$(1), 2)%.c: $(call get_path,$(1), 1)%.c
	python -m spinn_utilities.make_tools.converter $(call get_path,$(1),1) $(call get_path,$(1),2) $(APP_OUTPUT_DIR) $(DATABASE_KEY)
$(call get_path,$(1), 2)%.h: $(call get_path,$(1), 1)%.h
	python -m spinn_utilities.make_tools.converter $(call get_path,$(1),1) $(call get_path,$(1),2) $(APP_OUTPUT_DIR) $(DATABASE_KEY)

# Build the o files from the modified sources
$$(BUILD_DIR)%.o: $(call get_path,$(1),2)%.c
	# local
	-@mkdir -p $$(dir $$@)
	$$(CC) $$(CFLAGS) -o $$@ $$<
endef

define modified_dir#(src_dir)
	$(call get_path,$(1),2)
endef

# Add the default libraries and options
CFLAGS += -I $(FEC_DIR)/include
LFLAGS += -L$(FEC_DIR)/lib
LIBS += -lspinn_frontend_common

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

$(foreach d, $(SOURCE_DIRS), \
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
$(foreach d, $(SOURCE_DIRS), \
    $(eval $(call add_source_dir, $(d))))
OBJECTS += $(_OBJS)

SPINN_COMMON_INSTALL_DIR := $(strip $(if $(SPINN_COMMON_INSTALL_DIR), $(SPINN_COMMON_INSTALL_DIR), $(abspath $(FEC_DIR)/../../../spinn_common)))

# Bring in the common makefile
include $(SPINN_COMMON_INSTALL_DIR)/make/spinn_common.mk

# Tidy and cleaning dependencies
clean:
	$(RM) $(TEMP_FILES) $(OBJECTS) $(BUILD_DIR)$(APP).elf $(BUILD_DIR)$(APP).txt $(ALL_TARGETS) $(BUILD_DIR)$(APP).nm $(BUILD_DIR)$(APP).elf $(BUILD_DIR)$(APP).bin $(APP_CLEAN)
