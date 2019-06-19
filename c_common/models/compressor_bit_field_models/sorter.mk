APP = bit_field_sorter_and_searcher

SOURCES = bit_field_sorter_and_searcher.c

CFLAGS += -DSPINNAKER -Wshadow

include ../fec_models.mk

