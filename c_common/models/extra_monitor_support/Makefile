APP = extra_monitor_support
BUILD_DIR = build/
SOURCES = extra_monitor_support.c

CFLAGS += -Ofast
LFLAGS += -Ofast -Wl,--wrap=sark_int

SPINN_LIBS := $(SPINN_DIRS)/lib/libsark.a

include ../common.mk
