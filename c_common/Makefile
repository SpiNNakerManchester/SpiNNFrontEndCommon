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

INSTALL_DIRS = front_end_common_lib
BUILD_DIRS = models

# Locations of tag files
TAGFILES=sllt.tag common.tag
SLLT_TAG=http://spinnakermanchester.github.io/spinnaker_tools/sllt.tag
COMMON_TAG=http://spinnakermanchester.github.io/spinn_common/common.tag

DOXYGEN ?= doxygen
WGET ?= wget

all: install build
	
build: install $(BUILD_DIRS)
	@for d in $(BUILD_DIRS); do $(MAKE) -C $$d || exit $$?; done

install: $(INSTALL_DIRS)
	@for d in $(INSTALL_DIRS); do $(MAKE) -C $$d install || exit $$?; done

clean: $(BUILD_DIRS)
	@for d in $(BUILD_DIRS) $(INSTALL_DIRS); do $(MAKE) -C $$d clean || exit $$?; done
	@for d in $(INSTALL_DIRS); do $(MAKE) -C $$d install-clean || exit $$?; done

sllt.tag: .sllt_template.tag
	cp .sllt_template.tag sllt.tag
ifneq (, $(shell which $(WGET)))
	-$(WGET) -q -O sllt.tag $(SLLT_TAG)
endif 

common.tag: .common_template.tag
	cp .common_template.tag common.tag
ifneq (, $(shell which $(WGET)))
	-$(WGET) -q -O common.tag $(COMMON_TAG)
endif 

doxygen: $(TAGFILES)
	$(DOXYGEN)
doxysetup: $(TAGFILES)

.PHONY: all build install clean doxygen doxysetup
