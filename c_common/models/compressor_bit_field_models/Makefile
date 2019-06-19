APPS = compressor.mk sorter.mk

all: $(APPS)
	for f in $(APPS); do $(MAKE) -f $$f || exit $$?; done

%.aplx: %.mk
	"$(MAKE)" -f $*

clean: $(DIRS)
	for f in $(APPS); do $(MAKE) -f $$f clean || exit $$?; done
