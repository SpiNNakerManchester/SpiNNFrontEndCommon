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
$(2)%.c: $(1)%.c
	@python -m spinn_utilities.make_tools.converter $(1) $(2) $(2)log_dict.dict

$(2)%.h: $(1)%.h
	@python -m spinn_utilities.make_tools.converter $(1) $(2) $(2)log_dict.dict

$(2)log_dict.dict: $(1)
	@python -m spinn_utilities.make_tools.converter $(1) $(2) $(2)log_dict.dict

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
FEC_OPT = $(OTIME)
CFLAGS += -Wall -Wextra -D$(FEC_DEBUG) -D$(PROFILER) $(FEC_OPT) 

# Get the application name hash by running md5sum on application name and 
# extracting the first 8 bytes
SHELL = bash
APPLICATION_NAME_HASH = $(shell echo -n "$(APP)" | (md5sum 2>/dev/null || md5) | cut -c 1-8)
CFLAGS += -DAPPLICATION_NAME_HASH=0x$(APPLICATION_NAME_HASH)

# Add the modified directories to the include path
CFLAGS += $(foreach d, $(sort $(SOURCE_DIRS)), -I $(call modified_dir,$(d)))

# Sort out the set of dictionary files needed
MODIFIED_DICT_FILES := $(foreach d, $(sort $(SOURCE_DIRS)), $(call modified_dir, $(d))log_dict.dict)
LOG_DICT_FILES += $(wildcard $(SPINN_DIRS)/lib/*.dict)
LOG_DICT_FILES += $(MODIFIED_DICT_FILES)
APP_DICT_FILE = $(APP_OUTPUT_DIR)$(APP).dict

# default rule based on list ALL_TARGETS so more main targets can be added later
ALL_TARGETS += $(APP_DICT_FILE) $(APP_OUTPUT_DIR)$(APP).aplx
all: $(ALL_TARGETS)

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

$(APP_DICT_FILE): $(LOG_DICT_FILES)
	@echo mklogdict -o $(APP_DICT_FILE) $(LOG_DICT_FILES)
    # Add the two header lines once
	@head -2 $(firstword $(LOG_DICT_FILES)) > $(APP_DICT_FILE)
    # Add the none header lines for each file remembering tail starts counting at 1
	@$(foreach ldf, $(LOG_DICT_FILES), tail -n +3 $(ldf) >> $(APP_DICT_FILE) ;)

# Tidy and cleaning dependencies
clean:
	$(RM) $(TEMP_FILES) $(OBJECTS) $(BUILD_DIR)$(APP).elf $(BUILD_DIR)$(APP).txt $(ALL_TARGETS) $(LOG_DICT_FILE) $(BUILD_DIR)$(APP).nm $(BUILD_DIR)$(APP).elf $(BUILD_DIR)$(APP).bin
	rm -rf $(foreach d, $(sort $(SOURCE_DIRS)), $(call modified_dir, $(d)))

