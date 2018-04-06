ifndef RAW_DIR
   $(error RAW_DIR is not set.  Please define RAW_DIR)
endif

ifndef MODIFIED_DIR
   $(error MODIFIED_DIR is not set.  Please define MODIFIED_DIR)
endif

ifndef RANGE_FILE
    RANGE_FILE = $(abspath $(MODIFIED_DIR))/log_ranges.txt
endif

ifndef RANGE_START
    RANGE_START = 9000
endif

RAW_FILES = $(shell find $(RAW_DIR) -name '*.c')
RAW_FILES += $(shell find $(RAW_DIR) -name '*.h')

MODIFIED_FILES = $(RAW_FILES)
$(eval MODIFIED_FILES := $(MODIFIED_FILES:$(RAW_DIR)%=$(MODIFIED_DIR)%))

_DICT_FILES = $(RAW_FILES)
$(eval _DICT_FILES := $(_DICT_FILES:$(RAW_DIR)%.c=$(MODIFIED_DIR)%.cdict))
$(eval _DICT_FILES := $(_DICT_FILES:$(RAW_DIR)%.h=$(MODIFIED_DIR)%.hdict))
# _DICT_FILES += $(shell find $(SPINN_DIRS)/lib -name '*.csv')

#List the existing
OLD_CONVERT_FILES = $(RANGE_FILE)
OLD_CONVERT_FILES += $(shell find $(MODIFIED_DIR) -name '*.c')
OLD_CONVERT_FILES += $(shell find $(MODIFIED_DIR) -name '*.h')
OLD_CONVERT_FILES += $(shell find $(MODIFIED_DIR) -name '*.cdict')
OLD_CONVERT_FILES += $(shell find $(MODIFIED_DIR) -name '*.hdict')

# Rule to create all the modified c files
$(MODIFIED_DIR)/%.c $(MODIFIED_DIR)/%.cdict: $(RAW_DIR)/%.c
	python -m spinn_utilities.make_tools.file_convertor $< $(MODIFIED_DIR)/$*.c $(RANGE_FILE) $(RANGE_START)

# Rule to create all the modified h files
$(MODIFIED_DIR)/%.h $(MODIFIED_DIR)/%.hdict: $(_A_RAW_DIR)%.h
	python -m spinn_utilities.make_tools.file_convertor $< $(MODIFIED_DIR)/$*.h $(RANGE_FILE) $(RANGE_START)

# At the end we want all the csv files merged
$(APP_OUTPUT_DIR)$(APP).dict: $(_DICT_FILES)
	head -n 2 $(firstword $(_DICT_FILES)) > $(APP_OUTPUT_DIR)$(APP).dict
	$(foreach dict, $(_DICT_FILES), tail -n+3 $(dict) >> $(APP_OUTPUT_DIR)$(APP).dict;)

.PRECIOUS: $(MODIFIED_FILES) $(_DICT_FILES) $(APP_OUTPUT_DIR)$(APP).dict