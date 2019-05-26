NAME		:= pyprofibusphy
TARGET		:= tinyfpga_bx
TARGET_NAME	:= $(TARGET)_$(NAME)

DEBUG		:= 0

YOSYS		:= yosys
NEXTPNR		:= nextpnr
ICEPACK		:= icepack
ICETIME		:= icetime
ICEPLL		:= icepll
TINYPROG	:= tinyprog
PYTHON		:= python3
CAT		:= cat
GREP		:= grep
PRINTF		:= printf
RM		:= rm
FALSE		:= false
TR		:= tr

TARGET_LOWER	:= $(shell $(PRINTF) '%s' '$(TARGET)' | $(TR) A-Z a-z)
TARGET_UPPER	:= $(shell $(PRINTF) '%s' '$(TARGET)' | $(TR) a-z A-Z)

TOP_FILE	:= main.v
TOP_MODULE	:= top_module
PCF_FILE	:= $(TARGET_LOWER).pcf
PLL_MOD_V_FILE	:= pll_mod.v
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

ifeq ($(TARGET_LOWER),tinyfpga_bx)
CLK_HZ		:= 16000000
PLL_HZ		:= 24000000
PLL_MOD_V		:= $(PLL_MOD_V_FILE)
CLK_MHZ		:= $(shell expr $(CLK_HZ) / 1000000)
PLL_MHZ		:= $(shell expr $(PLL_HZ) / 1000000)
$(PLL_MOD_V):
	$(ICEPLL) -q -f $@ -m -n pll_module -i $(CLK_MHZ) -o $(PLL_MHZ)
else
CLK_HZ		:= 16000000
PLL_HZ		:= 16000000
PLL_MOD_V		:=
endif

crc8_func.v: crcgen.py
	$(PYTHON) crcgen.py --algorithm CRC-8-CCITT --verilog-function --name crc8 > $@

%.blif: $(TOP_FILE) $(wildcard *.v) $(GENERATED_V) $(PLL_MOD_V)
	$(YOSYS) -p 'read_verilog -DTARGET_$(TARGET_UPPER)=1 -DCLK_HZ=$(CLK_HZ) -DPLL_HZ=$(PLL_HZ) $(if $(filter-out 0,$(DEBUG)),-DDEBUG=1) $<' \
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
	-@$(PRINTF) '\n'
	-@$(GREP) -i -e 'Total' $@
	-@$(GREP) -i -Ee 'Max frequency|Max delay' $(NEXTPNR_LOG)
	-@$(PRINTF) '\n'
	-@$(GREP) --color=auto -H -n -i -e 'Warning' $(YOSYS_LOG) $(NEXTPNR_LOG) $(ICEPACK_LOG)
	-@$(PRINTF) '\n'
	-@$(GREP) -A6 -i -e 'Device utilisation' $(NEXTPNR_LOG)

install: $(TARGET_NAME).bin
	$(TINYPROG) -p $<

boot:
	$(TINYPROG) -b

clean:
	$(RM) -f *.blif *.json *.asc *.bin *.rpt $(YOSYS_LOG) $(NEXTPNR_LOG) $(ICEPACK_LOG) $(ICETIME_LOG) $(GENERATED_V) $(PLL_MOD_V_FILE)

.PHONY: all install boot clean
.PRECIOUS: %.json %.blif %.asc
