# SPINN_DIRS must be set for this file to be found

# APP_OUTPUT_DIR directory to save a and dict files to (none installed)
# APP_OUTPUT_DIR must end with /
ifndef APP_OUTPUT_DIR
    $(error APP_OUTPUT_DIR is not set.  Please define APP_OUTPUT_DIR)
endif

# APP name for a and dict files
ifndef APP
    $(error APP is not set.  Please define APP)
endif

# BUILD_DIR local directory to put o files into
ifndef BUILD_DIR
    BUILD_DIR := build/
endif

# MODIFIED_DIR local directory to put modified c and h files into
ifndef MODIFIED_DIR
    MODIFIED_DIR := modified_src/
endif

# SRC_DIR local directory where the raw c and h files are 
ifndef SRC_DIR
    SRC_DIR := src/
endif

# SOURCES one or more unmodified c files to build
# While these file will be in the SRC_DIR that will not be included in SOURCES
# SOURCES can be in sub directories of SRC_DIR in which case the sub directory is included
ifndef SOURCES
    $(error SOURCES is not set.  Please define SOURCES)
endif

# Convert the objs into the correct format to work here
_OBJS := $(SOURCES)
$(eval _OBJS := $(_OBJS:%.c=$(BUILD_DIR)%.o))
OBJECTS += $(_OBJS)

LIBRARIES += -lspinn_frontend_common -lspinn_common -lm
FEC_DEBUG := PRODUCTION_CODE
PROFILER := PROFILER_DISABLED

# Run md5sum on application name and extract first 8 bytes
SHELL = bash
APPLICATION_NAME_HASH = $(shell echo -n "$(APP)" | (md5sum 2>/dev/null || md5) | cut -c 1-8)

FEC_OPT = $(OTIME)
CFLAGS += -Wall -Wextra -D$(FEC_DEBUG) -D$(PROFILER) $(FEC_OPT) -DAPPLICATION_NAME_HASH=0x$(APPLICATION_NAME_HASH)

MODIFIED_DICT_FILE = $(MODIFIED_DIR)log_dict.dict

LOG_DICT_FILES += $(wildcard $(SPINN_DIRS)/lib/*.dict)
LOG_DICT_FILES += $(MODIFIED_DICT_FILE)
APP_DICT_FILE = $(APP_OUTPUT_DIR)$(APP).dict

ALL_TARGETS += $(APP_OUTPUT_DIR)$(APP).aplx $(APP_DICT_FILE)

# default rule based on list ALL_TARGETS so more main targets can be added later
all: $(ALL_TARGETS)

# All the c and h files built at the same time but individual rules needed for make chains
$(MODIFIED_DIR)%.c: $(SRC_DIR)%.c
	python -m spinn_utilities.make_tools.convertor $(SRC_DIR) $(MODIFIED_DIR) $(MODIFIED_DICT_FILE)

$(MODIFIED_DIR)%.h: $(SRC_DIR)%.h
	python -m spinn_utilities.make_tools.convertor $(SRC_DIR) $(MODIFIED_DIR) $(MODIFIED_DICT_FILE)

$(MODIFIED_DICT_FILE): $(SRC_DIR)
	python -m spinn_utilities.make_tools.convertor $(SRC_DIR) $(MODIFIED_DIR) $(MODIFIED_DICT_FILE)

# Build the o files from the modified sources and any copied directories (if applicable)
$(BUILD_DIR)%.o: $(MODIFIED_DIR)%.c $(COPIED_DIRS)
	# local
	-mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -o $@ $<

include $(SPINN_DIRS)/make/spinnaker_tools.mk

$(APP_DICT_FILE): $(LOG_DICT_FILES)
    # Add the two header lines once
	head -2 $(firstword $(LOG_DICT_FILES)) > $(APP_DICT_FILE)
	# Add the none header lines for each file remembering tail starts counting at 1
	$(foreach ldf, $(LOG_DICT_FILES), tail -n +3 $(ldf) >> $(APP_DICT_FILE) ;)

# Tidy and cleaning dependencies
clean:
	$(RM) $(TEMP_FILES) $(OBJECTS) $(BUILD_DIR)$(APP).elf $(BUILD_DIR)$(APP).txt $(ALL_TARGETS) $(LOG_DICT_FILE)
	rm -rf $(MODIFIED_DIR)

