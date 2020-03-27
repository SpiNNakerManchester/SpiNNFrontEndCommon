# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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
OBJS = data_specification.o simulation.o recording.o profiler.o
BUILD_OBJS = $(OBJS:%.o=$(SPINN_COMMON_BUILD)/%.o)

# Headers
HEADERS = common-typedefs.h data_specification.h simulation.h recording.h profiler.h buffered_eieio_defs.h debug.h eieio.h
INSTALL_HEADERS = $(HEADERS:%.h=$(SPINN_INC_DIR)/%.h)

# Makefile
MAKEFILES = local.mk Makefile.SpiNNFrontEndCommon FrontEndCommon.mk
INSTALL_MAKEFILES = $(MAKEFILES:%=$(SPINN_MAKE_LIB_DIR)/%)

# Libraries
APP = libspinn_frontend_common
LIBS = $(APP).a
INSTALL_LIBS = $(LIBS:%=$(SPINN_LIB_DIR)/%)

# Log Dictionary file
LOG_DICT_FILE = $(SPINN_LIB_DIR)/$(APP).dict

# Ensure $(INSTALL) is defined, even on MinGW
INSTALL ?= install

# Variables needed for file converter
SRC_DIR = src/
MODIFIED_DIR = modified_src/

# Build rules (default)
$(SPINN_COMMON_BUILD)/$(APP).a: $(BUILD_OBJS)
	@$(RM) $@
	$(AR) $@ $(BUILD_OBJS)

$(MODIFIED_DIR)%.c: $(RAW_DIR)
	python -m spinn_utilities.make_tools.converter $(SRC_DIR) $(MODIFIED_DIR) $(LOG_DICT_FILE)

$(LOG_DICT_FILE): $(RAW_DIR)
	python -m spinn_utilities.make_tools.converter $(SRC_DIR) $(MODIFIED_DIR) $(LOG_DICT_FILE)

$(SPINN_COMMON_BUILD)/%.o: $(MODIFIED_DIR)/%.c $(SPINN_COMMON_BUILD) $(LOG_DICT_FILE)
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

$(SPINN_LIB_DIR)/%.dict: $(SPINN_COMMON_BUILD)/%.dict
	$(INSTALL) -c -m644 $< $(SPINN_LIB_DIR)

$(SPINN_INC_DIR)/%.h: include/%.h
	$(INSTALL) -c -m644 $< $(SPINN_INC_DIR)

$(SPINN_MAKE_LIB_DIR)/%: %
	$(INSTALL) -c -m644 $< $(SPINN_MAKE_LIB_DIR)

clean:
	$(RM) $(SPINN_COMMON_BUILD)/$(APP).a $(BUILD_OBJS) $(OLD_CONVERT_FILES)
	rm -rf $(MODIFIED_DIR)

install-clean:
	$(RM) $(INSTALL_LIBS) $(INSTALL_HEADERS) $(SPINN_LIB_DIR)/*.dict $(SPINN_LIB_DIR)/*.ranges

.PRECIOUS: $(MODIFIED_DIR)%.c $(LOG_DICT_FILE) $(BUILD_DIR)%.nm $(BUILD_DIR)%.elf $(BUILD_DIR)%.bin

.PHONY: clean install install-libraries install-headers install-makefiles install-clean

test:
	#$(APP_OUTPUT_DIR)$(APP).dict
	#$(INSTALL_LIBS)
