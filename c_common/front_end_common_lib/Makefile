# Copyright (c) 2014 The University of Manchester
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

FEC_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
FEC_BUILD = $(FEC_DIR)/build
FEC_LIB = $(FEC_DIR)/lib
override LIB := 1

ifndef SPINN_COMMON_INSTALL_DIR:
    # assume parallel clone
    SPINN_COMMON_INSTALL_DIR := $(FEC_DIR)../../../spinn_common
endif

include $(SPINN_COMMON_INSTALL_DIR)/make/spinn_common.mk

ifndef PRINT_DEBUG
    PRINT_DEBUG = PRODUCTION_CODE
endif

CFLAGS += $(OSPACE) -I $(FEC_DIR)/include -D$(PRINT_DEBUG)

# Objects
OBJS = data_specification.o simulation.o recording.o profiler.o \
       malloc_extras.o
BUILD_OBJS = $(OBJS:%.o=$(FEC_BUILD)/%.o)

# Headers
HEADERS = common-typedefs.h data_specification.h simulation.h recording.h \
          profiler.h buffered_eieio_defs.h debug.h eieio.h sdp_no_scp.h \
          filter_info.h key_atom_map.h malloc_extras.h spinn_extra.h \
          wfi.h

# Libraries
APP = libspinn_frontend_common
override LIB := 1

# Ensure $(INSTALL) is defined, even on MinGW
INSTALL ?= install

# Variables needed for file converter
SRC_DIR = $(FEC_DIR)/src/
MODIFIED_DIR = $(FEC_DIR)/modified_src/

# Build rules (default)
$(FEC_LIB)/$(APP).a: $(BUILD_OBJS)
	$(MKDIR) $(FEC_BUILD)
	$(MKDIR) $(FEC_LIB)
	@$(RM) $@
	$(AR) $@ $(BUILD_OBJS)

$(MODIFIED_DIR)%.c: $(RAW_DIR)
	python -m spinn_utilities.make_tools.converter $(SRC_DIR) $(MODIFIED_DIR) True

$(FEC_BUILD)/%.o: $(MODIFIED_DIR)/%.c
	$(CC) $(CFLAGS) -o $@ $<

# Installing rules
install: $(FEC_LIB)/$(APP).a
	$(eval FEC_INSTALL_DIR := $(strip $(if $(FEC_INSTALL_DIR), $(FEC_INSTALL_DIR), $(if $(SPINN_DIRS), $(SPINN_DIRS)/fec_install, $(error FEC_INSTALL_DIR or SPINN_DIRS is not set.  Please define FEC_INSTALL_DIR or SPINN_DIRS)))))
	$(MKDIR) $(FEC_INSTALL_DIR)/lib
	$(MKDIR) $(FEC_INSTALL_DIR)/include
	$(MKDIR) $(FEC_INSTALL_DIR)/make
	$(INSTALL) -c -m644 $< $(FEC_INSTALL_DIR)/lib
	$(INSTALL) -c -m644 $(HEADERS:%=$(FEC_DIR)/include/%) $(FEC_INSTALL_DIR)/include
	$(INSTALL) -c -m644 $(FEC_DIR)/fec.mk $(FEC_INSTALL_DIR)/make

clean:
	$(RM) $(FEC_BUILD)/$(APP).a $(BUILD_OBJS)
	rm -rf $(MODIFIED_DIR)
	$(RM) $(FEC_BUILD)/logs.sqlite3

.PRECIOUS: $(MODIFIED_DIR)%.c $(BUILD_DIR)%.nm $(BUILD_DIR)%.elf $(BUILD_DIR)%.bin

.PHONY: clean install

test:
	#$(APP_OUTPUT_DIR)$(APP).dict
	#$(INSTALL_LIBS)
