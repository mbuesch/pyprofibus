# Project name
NAME		:= pyprofibusphy

# Target board configuration
TARGET		:= tinyfpga_bx
PLL_HZ		:= 24000000

DEBUG		:= 0

# Source files
TOP_FILE	:= main.v
TOP_MODULE	:= top_module
PCF_FILE	:= $(TARGET).pcf

# Generated files
PLL_MOD_V_FILE	:= pll_mod.v
GENERATED_V	:= crc8_func.v

# Extra dependencies
EXTRA_DEP_V	:=
EXTRA_DEP_PY	:=

# Additional cleanup
CLEAN_FILES	:= crcgen.stamp

include fpgamakelib/fpgamakelib.mk

crcgen.stamp:
	$(TEST) -f ./crcgen/crcgen || $(GIT) submodule update --init
	$(TOUCH) $@

crc8_func.v: crcgen.stamp
	PYTHONPATH=./crcgen $(PYTHON) ./crcgen/crcgen --algorithm CRC-8-CCITT --verilog-function --name crc8 > $@
