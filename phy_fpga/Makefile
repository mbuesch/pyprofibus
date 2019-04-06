NAME		:= pyprofibus_fpga_phy

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

YOSYS_SYNTH	:= synth_ice40
PNR_PACKAGE	:= cm81
NEXTPNR_ARCH	:= ice40
DEVICE		:= lp8k
TOP_FILE	:= main.v
TOP_MODULE	:= top_module
PCF_FILE	:= tinyfpga_bx.pcf
GENERATED_V	:= crc8_func.v

YOSYS_LOG	:= yosys.log
NEXTPNR_LOG	:= nextpnr.log
ICEPACK_LOG	:= icepack.log
ICETIME_LOG	:= icetime.log
LOG		= >$(1) 2>&1 || ( $(CAT) $(1); $(FALSE) )

.DEFAULT_GOAL := all
all: $(NAME).bin $(NAME).rpt

crc8_func.v: crcgen.py
	$(PYTHON) crcgen.py --nr-bits 8 --polynomial 7 --verilog-function --name crc8 > $@

%.blif: $(TOP_FILE) $(wildcard *.v) $(GENERATED_V)
	$(YOSYS) -p '$(YOSYS_SYNTH) -top $(TOP_MODULE) -json $(patsubst %.blif,%.json,$@) -blif $@' $< $(call LOG,$(YOSYS_LOG))

%.asc: $(PCF_FILE) %.blif
	$(NEXTPNR)-$(NEXTPNR_ARCH) --$(DEVICE) --package $(PNR_PACKAGE) --json $(NAME).json --pcf $< --asc $@ $(call LOG,$(NEXTPNR_LOG))

%.bin: %.asc
	$(ICEPACK) $< $@ $(call LOG,$(ICEPACK_LOG))

%.rpt: %.asc %.bin
	$(ICETIME) -d $(DEVICE) -p $(PCF_FILE) -m -t -r $@ $< $(call LOG,$(ICETIME_LOG))
	-@$(ECHO)
	-@$(GREP) -i -e 'Total' $@
	-@$(GREP) -i -Ee 'Max frequency|Max delay' $(NEXTPNR_LOG)
	-@$(ECHO)
	-@$(GREP) --color=auto -H -n -i -e 'Warning' $(YOSYS_LOG) $(NEXTPNR_LOG) $(ICEPACK_LOG)
	-@$(ECHO)
	-@$(GREP) -A6 -i -e 'Device utilisation' $(NEXTPNR_LOG)

install: $(NAME).bin
	$(TINYPROG) -p $<

boot:
	$(TINYPROG) -b

clean:
	$(RM) -f *.blif *.json *.asc *.bin *.rpt $(YOSYS_LOG) $(NEXTPNR_LOG) $(ICEPACK_LOG) $(ICETIME_LOG) $(GENERATED_V)

.PHONY: all install boot clean
.PRECIOUS: %.json %.blif %.asc
