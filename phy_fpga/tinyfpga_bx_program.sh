#!/bin/sh
set -e
tinyprog --update-bootloader
tinyprog --program tinyfpga_bx_pyprofibusphy.bin
