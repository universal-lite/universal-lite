LOCALEDIR = ../files/usr/share/locale
LANGUAGES = am ar de es fa fr ha hi it ja ko nl pl pt ru sv sw th tr vi yo zh

# --- Wizard domain ---
WIZARD_DOMAIN = universal-lite-setup-wizard
WIZARD_SOURCE = ../files/usr/bin/$(WIZARD_DOMAIN)
WIZARD_POT = $(WIZARD_DOMAIN).pot
WIZARD_PO = $(LANGUAGES:%=%.po)
WIZARD_MO = $(LANGUAGES:%=$(LOCALEDIR)/%/LC_MESSAGES/$(WIZARD_DOMAIN).mo)

# --- Settings domain ---
SETTINGS_DOMAIN = universal-lite-settings
SETTINGS_POT = settings/$(SETTINGS_DOMAIN).pot
SETTINGS_PO = $(LANGUAGES:%=settings/%.po)
SETTINGS_MO = $(LANGUAGES:%=$(LOCALEDIR)/%/LC_MESSAGES/$(SETTINGS_DOMAIN).mo)

SETTINGS_SOURCES = \
	../files/usr/bin/universal-lite-settings \
	../files/usr/bin/universal-lite-greeter \
	../files/usr/lib/universal-lite/settings/app.py \
	../files/usr/lib/universal-lite/settings/base.py \
	../files/usr/lib/universal-lite/settings/settings_store.py \
	../files/usr/lib/universal-lite/settings/window.py \
	../files/usr/lib/universal-lite/settings/pages/__init__.py \
	$(wildcard ../files/usr/lib/universal-lite/settings/pages/[a-z]*.py)

.PHONY: pot po mo clean all

# --- Wizard targets ---
pot-wizard: $(WIZARD_POT)

$(WIZARD_POT): $(WIZARD_SOURCE)
	xgettext --language=Python --keyword=_ --keyword=N_ \
	    --keyword=_make_translated_label \
	    --keyword=_make_summary_row:2 \
	    --output=$(WIZARD_POT) --from-code=UTF-8 \
	    --package-name="$(WIZARD_DOMAIN)" \
	    $(WIZARD_SOURCE)

po-wizard: $(WIZARD_PO)

%.po: $(WIZARD_POT)
	@if [ -f $@ ]; then \
	    msgmerge --update --no-fuzzy-matching $@ $(WIZARD_POT); \
	else \
	    msginit --input=$(WIZARD_POT) --output=$@ --locale=$* --no-translator; \
	fi

mo-wizard: $(WIZARD_MO)

$(LOCALEDIR)/%/LC_MESSAGES/$(WIZARD_DOMAIN).mo: %.po
	@mkdir -p $(dir $@)
	msgfmt --output=$@ $<

# --- Settings targets ---
pot-settings: $(SETTINGS_POT)

$(SETTINGS_POT): $(SETTINGS_SOURCES)
	@mkdir -p settings
	xgettext --language=Python --keyword=_ --keyword=N_ \
	    --output=$(SETTINGS_POT) --from-code=UTF-8 \
	    --package-name="$(SETTINGS_DOMAIN)" \
	    $(SETTINGS_SOURCES)

po-settings: $(SETTINGS_PO)

settings/%.po: $(SETTINGS_POT)
	@mkdir -p settings
	@if [ -f $@ ]; then \
	    msgmerge --update --no-fuzzy-matching $@ $(SETTINGS_POT); \
	else \
	    msginit --input=$(SETTINGS_POT) --output=$@ --locale=$* --no-translator; \
	fi

mo-settings: $(SETTINGS_MO)

$(LOCALEDIR)/%/LC_MESSAGES/$(SETTINGS_DOMAIN).mo: settings/%.po
	@mkdir -p $(dir $@)
	msgfmt --output=$@ $<

# --- Combined targets ---
pot: pot-wizard pot-settings
po: po-wizard po-settings
mo: mo-wizard mo-settings

clean:
	rm -f $(WIZARD_POT) $(SETTINGS_POT)
	rm -f $(WIZARD_MO) $(SETTINGS_MO)

all: pot po mo
