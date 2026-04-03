DOMAIN = universal-lite-setup-wizard
SOURCE = ../files/usr/bin/$(DOMAIN)
POTFILE = $(DOMAIN).pot
LOCALEDIR = ../files/usr/share/locale

LANGUAGES = am ar de es fa fr ha hi it ja ko nl pl pt ru sv sw th tr vi yo zh

PO_FILES = $(LANGUAGES:%=%.po)
MO_FILES = $(LANGUAGES:%=$(LOCALEDIR)/%/LC_MESSAGES/$(DOMAIN).mo)

.PHONY: pot po mo clean all

pot: $(POTFILE)

$(POTFILE): $(SOURCE)
	xgettext --language=Python --keyword=_ --keyword=N_ \
	    --output=$(POTFILE) --from-code=UTF-8 \
	    --package-name="$(DOMAIN)" \
	    $(SOURCE)

po: $(PO_FILES)

%.po: $(POTFILE)
	@if [ -f $@ ]; then \
	    msgmerge --update --no-fuzzy-matching $@ $(POTFILE); \
	else \
	    msginit --input=$(POTFILE) --output=$@ --locale=$* --no-translator; \
	fi

mo: $(MO_FILES)

$(LOCALEDIR)/%/LC_MESSAGES/$(DOMAIN).mo: %.po
	@mkdir -p $(dir $@)
	msgfmt --output=$@ $<

clean:
	rm -f $(POTFILE)
	rm -f $(MO_FILES)

all: pot po mo
