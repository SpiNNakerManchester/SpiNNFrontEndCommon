# If SPINN_DIRS is not defined, this is an error!
ifndef SPINN_DIRS
    $(error SPINN_DIRS is not set.  Please define SPINN_DIRS (possibly by running "source setup" in the spinnaker tools folder))
endif

SPINN_COMMON_BUILD = build
override LIB := 1
include $(SPINN_DIRS)/make/Makefile.common

ifndef PRINT_DEBUG
    PRINT_DEBUG = PRODUCTION_CODE
endif

CFLAGS += $(OSPACE) -I include -D$(PRINT_DEBUG)
LDFLAGS += -lspinn_common

# Objects
OBJS = data_specification.o simulation.o recording.o profiler.o
BUILD_OBJS = $(OBJS:%.o=$(SPINN_COMMON_BUILD)/%.o)

# Headers
HEADERS = common-typedefs.h data_specification.h simulation.h recording.h profiler.h buffered_eieio_defs.h
INSTALL_HEADERS = $(HEADERS:%.h=$(SPINN_INC_DIR)/%.h)

# Makefile
MAKEFILES = Makefile.SpiNNFrontEndCommon FrontEndCommon.mk local.mk
INSTALL_MAKEFILES = $(MAKEFILES:%=$(SPINN_MAKE_LIB_DIR)/%)

# Libraries
LIBS = libspinn_frontend_common.a
INSTALL_LIBS = $(LIBS:%.a=$(SPINN_LIB_DIR)/%.a)

# Ensure $(INSTALL) is defined, even on MinGW
INSTALL ?= install

# Build rules (default)
$(SPINN_COMMON_BUILD)/libspinn_frontend_common.a: $(BUILD_OBJS) 
	$(RM) $@
	$(AR) $@ $(BUILD_OBJS)

$(SPINN_COMMON_BUILD)/%.o: src/%.c $(SPINN_COMMON_BUILD)
	$(CC) $(CFLAGS) -o $@ $<

$(SPINN_COMMON_BUILD):
	$(MKDIR) $@

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
	$(RM) $(SPINN_COMMON_BUILD)/libspinn_frontend_common.a $(BUILD_OBJS)

install-clean:
	$(RM) $(INSTALL_LIBS) $(INSTALL_HEADERS) $(INSTALL_MAKEFILES)

.PHONY: clean install install-libraries install-headers install-makefiles install-clean
