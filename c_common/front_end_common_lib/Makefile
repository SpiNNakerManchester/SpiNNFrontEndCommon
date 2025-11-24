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

# If SPINN_DIRS is not defined, this is an error!
ifndef SPINN_DIRS
    $(error SPINN_DIRS is not set.  Please define SPINN_DIRS (possibly by running "source setup" in the spinnaker tools folder))
endif

SPINN_COMMON_BUILD = build
override LIB := 1
include $(SPINN_DIRS)/make/spinnaker_tools.mk

ifndef PRINT_DEBUG
    PRINT_DEBUG = PRODUCTION_CODE
endif

CFLAGS += $(OSPACE) -I include -D$(PRINT_DEBUG)
LDFLAGS += -lspinn_common

# Objects
OBJS = data_specification.o simulation.o recording.o profiler.o \
       malloc_extras.o
BUILD_OBJS = $(OBJS:%.o=$(SPINN_COMMON_BUILD)/%.o)

# Headers
HEADERS = common-typedefs.h data_specification.h simulation.h recording.h \
          profiler.h buffered_eieio_defs.h debug.h eieio.h sdp_no_scp.h \
          filter_info.h key_atom_map.h malloc_extras.h spinn_extra.h \
          wfi.h
INSTALL_HEADERS = $(HEADERS:%.h=$(SPINN_INC_DIR)/%.h)

# Makefile
DATABASE_KEY = F
MAKEFILES = local.mk Makefile.SpiNNFrontEndCommon FrontEndCommon.mk
INSTALL_MAKEFILES = $(MAKEFILES:%=$(SPINN_MAKE_LIB_DIR)/%)

# Libraries
APP = libspinn_frontend_common
LIBS = $(APP).a
INSTALL_LIBS = $(LIBS:%=$(SPINN_LIB_DIR)/%)

# Ensure $(INSTALL) is defined, even on MinGW
INSTALL ?= install

# Variables needed for file converter
SRC_DIR = src/
MODIFIED_DIR = modified_src/

APP_OUTPUT_DIR := $(abspath $(CURRENT_DIR)../../spinn_front_end_common/common_model_binaries/)/

# Build rules (default)
$(SPINN_COMMON_BUILD)/$(APP).a: $(BUILD_OBJS)
	@$(RM) $@
	$(AR) $@ $(BUILD_OBJS)

$(MODIFIED_DIR)%.c: $(RAW_DIR)
	python -m spinn_utilities.make_tools.converter $(SRC_DIR) $(MODIFIED_DIR) c $(APP_OUTPUT_DIR)/logs.sqlite3

$(SPINN_COMMON_BUILD)/%.o: $(MODIFIED_DIR)/%.c $(SPINN_COMMON_BUILD)
	$(CC) $(CFLAGS) -o $@ $<

$(SPINN_COMMON_BUILD):
	@$(MKDIR) $@

# Installing rules
install: install-libraries install-headers install-makefiles
install-libraries: $(INSTALL_LIBS)
install-headers: $(INSTALL_HEADERS)
install-makefiles: $(INSTALL_MAKEFILES)

$(SPINN_LIB_DIR)/%.a: $(SPINN_COMMON_BUILD)/%.a
	$(INSTALL) -c -m644 $< $(SPINN_LIB_DIR)

$(SPINN_INC_DIR)/%.h: include/%.h
	$(INSTALL) -c -m644 $< $(SPINN_INC_DIR)

$(SPINN_MAKE_LIB_DIR)/%: %
	$(INSTALL) -c -m644 $< $(SPINN_MAKE_LIB_DIR)

clean:
	$(RM) $(SPINN_COMMON_BUILD)/$(APP).a $(BUILD_OBJS) $(OLD_CONVERT_FILES)
	rm -rf $(MODIFIED_DIR)

install-clean:
	$(RM) $(INSTALL_LIBS) $(INSTALL_HEADERS) $(APP_OUTPUT_DIR)/logs.sqlite3

.PRECIOUS: $(MODIFIED_DIR)%.c $(BUILD_DIR)%.nm $(BUILD_DIR)%.elf $(BUILD_DIR)%.bin

.PHONY: clean install install-libraries install-headers install-makefiles install-clean

test:
	#$(APP_OUTPUT_DIR)$(APP).dict
	#$(INSTALL_LIBS)
