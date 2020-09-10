PYS		:=
BOOTPY		:= boot.py
MAINPY		:= main.py
MAINPYDIR	:=
GSDS		:=
CONFS		:=

SRCDIR		:=
BUILDDIR	:=

MARCH		:= xtensawin
MPYCROSS_OPTS	:= -O0
GSDPARSER_OPTS	:= --dump-strip --dump-notext --dump-noextuserprmdata

MPYCROSS	:= mpy-cross
GSDPARSER	:= $(SRCDIR)/gsdparser
MKDIR		:= mkdir
CP		:= cp
RM		:= rm

_MPYS		= $(sort $(patsubst %.py,$(2)/%.mpy,$(1)))
_GSDMPYS	= $(sort $(patsubst %.gsd,$(2)/%_gsd.mpy,$(1)))
_GSDPYS		= $(sort $(patsubst %.gsd,$(2)/%_gsd.py,$(1)))
_CONFS		= $(sort $(patsubst %.conf,$(2)/%.conf,$(1)))
_MPYCROSS	= $(MPYCROSS) "$(1)" -s "$(2)" -march="$(MARCH)" $(MPYCROSS_OPTS) -o "$(3)"

all: $(call _MPYS,$(PYS),$(BUILDDIR)) \
     $(call _GSDMPYS,$(GSDS),$(BUILDDIR)) \
     $(call _CONFS,$(CONFS),$(BUILDDIR)) \
     $(BUILDDIR)/$(BOOTPY) \
     $(BUILDDIR)/$(MAINPY)

$(BUILDDIR)/%.mpy: %.py
	@$(MKDIR) -p "$(dir $@)"
	$(call _MPYCROSS,$<,$(shell basename "$<"),$@)

$(BUILDDIR)/%_gsd.mpy: %.gsd
	@$(MKDIR) -p "$(dir $@)"
	$(GSDPARSER) -D $(GSDPARSER_OPTS) -o "$(call _GSDPYS,$<,$(BUILDDIR))" "$<"
	$(call _MPYCROSS,$(call _GSDPYS,$<,$(BUILDDIR)),$(shell basename "$(call _GSDPYS,$<,$(BUILDDIR))"),$@)
	$(RM) "$(call _GSDPYS,$<,$(BUILDDIR))"

$(BUILDDIR)/%.conf: %.conf
	@$(MKDIR) -p "$(dir $@)"
	$(CP) "$<" "$@"

$(BUILDDIR)/$(BOOTPY) $(BUILDDIR)/$(MAINPY): $(BUILDDIR)/%.py: $(MAINPYDIR)/%.py
	@$(MKDIR) -p "$(dir $@)"
	$(CP) "$<" "$@"

clean:
	$(RM) -rf $(BUILDDIR)

.PHONY: all clean
