NAME		:= pyprofibus
TARGET		:= tinyfpga_bx
TARGET_NAME	:= $(TARGET)_$(NAME)

YOSYS		:= yosys
NEXTPNR		:= nextpnr
ICEPACK		:= icepack
ICETIME		:= icetime
TINYPROG	:= tinyprog
PYTHON		:= python3
CAT		:= cat
GREP		:= grep
ECHO		:= echo
RM		:= rm
FALSE		:= false

TARGET_LOWER	:= $(shell printf '%s' '$(TARGET)' | tr A-Z a-z)
TARGET_UPPER	:= $(shell printf '%s' '$(TARGET)' | tr a-z A-Z)

TOP_FILE	:= main.v
TOP_MODULE	:= top_module
PCF_FILE	:= $(TARGET_LOWER).pcf
GENERATED_V	:= crc8_func.v

ifeq ($(TARGET_LOWER),tinyfpga_bx)
YOSYS_SYNTH_CMD	= 'synth_ice40 -top $(TOP_MODULE) -json $(patsubst %.blif,%.json,$@) -blif $@'
PNR_PACKAGE	:= cm81
NEXTPNR_ARCH	:= ice40
DEVICE		:= lp8k
else
$(error TARGET $(TARGET) is invalid)
endif

YOSYS_LOG	:= $(TARGET_NAME)_yosys.log
NEXTPNR_LOG	:= $(TARGET_NAME)_nextpnr.log
ICEPACK_LOG	:= $(TARGET_NAME)_icepack.log
ICETIME_LOG	:= $(TARGET_NAME)_icetime.log
LOG		= >$(1) 2>&1 || ( $(CAT) $(1); $(FALSE) )

.DEFAULT_GOAL := all
all: $(TARGET_NAME).bin $(TARGET_NAME).rpt

crc8_func.v: crcgen.py
	$(PYTHON) crcgen.py --nr-bits 8 --polynomial 0x07 --verilog-function --name crc8 > $@

%.blif: $(TOP_FILE) $(wildcard *.v) $(GENERATED_V)
	$(YOSYS) -p 'read_verilog -DTARGET_$(TARGET_UPPER)=1 $<' \
		-p $(YOSYS_SYNTH_CMD) \
		$(call LOG,$(YOSYS_LOG))

%.asc: $(PCF_FILE) %.blif
	$(NEXTPNR)-$(NEXTPNR_ARCH) --$(DEVICE) --package $(PNR_PACKAGE) --json $(TARGET_NAME).json --pcf $< --asc $@ \
		$(call LOG,$(NEXTPNR_LOG))

%.bin: %.asc
	$(ICEPACK) $< $@ $(call LOG,$(ICEPACK_LOG))

%.rpt: %.asc %.bin
	$(ICETIME) -d $(DEVICE) -p $(PCF_FILE) -m -t -r $@ $< \
		$(call LOG,$(ICETIME_LOG))
	-@$(ECHO)
	-@$(GREP) -i -e 'Total' $@
	-@$(GREP) -i -Ee 'Max frequency|Max delay' $(NEXTPNR_LOG)
	-@$(ECHO)
	-@$(GREP) --color=auto -H -n -i -e 'Warning' $(YOSYS_LOG) $(NEXTPNR_LOG) $(ICEPACK_LOG)
	-@$(ECHO)
	-@$(GREP) -A6 -i -e 'Device utilisation' $(NEXTPNR_LOG)

install: $(TARGET_NAME).bin
	$(TINYPROG) -p $<

boot:
	$(TINYPROG) -b

clean:
	$(RM) -f *.blif *.json *.asc *.bin *.rpt $(YOSYS_LOG) $(NEXTPNR_LOG) $(ICEPACK_LOG) $(ICETIME_LOG) $(GENERATED_V)

.PHONY: all install boot clean
.PRECIOUS: %.json %.blif %.asc
