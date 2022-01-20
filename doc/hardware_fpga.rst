pyprofibus FPGA PHY documentation
=================================

Instead of using the serial port of the host computer to connect to the Profibus network an FPGA can be used. That improves the realtime capabilities and the speed of the pyprofibus system.


FPGA boards
===========

Currently only the `TinyFPGA BX <https://tinyfpga.com/>`_ is supported as FPGA.

However it's possible to add support for other FPGAs. The TinyFPGA BX has been chosen, because it has a fully Open Source toolchain. So the pyprofibus FPGA Verilog sources can be translated to the binary FPGA bitstream using only freely available tools.

The pyprofibus releases come with pre-built bitstream images. So there's no need for the user to install the toolchain and build the FPGA bitstream. The only tool that is needed is the "flashing/programming tool" that is used to transfer the binary bitstream to the FPGA board.


Flashing / Programming tool
---------------------------

For the purpose of writing/downloading/flashing the binary FPGA bitstream to the TinyFPGA BX board the `tinyprog <https://github.com/tinyfpga/TinyFPGA-Bootloader/>`_ tool can be used.

The helper script `tinyfpga_bx_program.sh` shipped with pyprofibus in the subdirectory `phy_fpga/bin/tinyfpga_bx` can be used to conveniently call `tinyprog` with the correct parameters. Just connect the TinyFPGA BX board via USB to the computer and run the `tinyfpga_bx_program.sh` script. It does everything to program the pyprofibus PHY to your TinyFPGA BX.

Build toolchain
---------------

If you want to modify the FPGA sources and build your own version of the FPGA bitstream, the following tools are required:


Project IceStorm
~~~~~~~~~~~~~~~~

The `Project IceStorm <http://bygone.clairexen.net/icestorm/>`_ is needed to build the bitstream for the TinyFPGA BX board.


Yosys
~~~~~

The `Yosys Open SYnthesis Suite <https://yosyshq.net/yosys/>`_ is required to synthesize the Verilog sources.


nextpnr
~~~~~~~

The `nextpnr FPGA place and route tool <https://github.com/YosysHQ/nextpnr>`_ is required for FPGA routing.


Python
~~~~~~

`Python 3.7 <https://www.python.org/>`_ or later is required to auto-generate some parts of the sources.


GNU make an other standard GNU/Linux shell utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`GNU make <https://www.gnu.org/software/make/>`_ and various other standard GNU/Linux shell utilities, that are already installed on any Desktop Linux distribution. Building on Windows is not supported.


Downloading and installing all toolchain tools
----------------------------------------------

The script `build_fpga_toolchain.sh` that is included in the pyprofibus archive can be used to download, build and install all FPGA toolchain tools to the `$HOME` directory.

Just run the script as follows. It will download all required packages, build and install everything to `$HOME/fpga-toolchain` by default.

.. code:: sh

	cd phy_fpga/fpgamakelib
	./build_fpga_toolchain.sh

After successful execution of `build_fpga_toolchain.sh` please read the information about `$PATH` that the script prints to the console. The line printed by the script shall be added to your `$HOME/.bashrc`

No changes to the operating system are necessary. Do *not* run `build_fpga_toolchain.sh` as root.

The toolchain can be uninstalled by simply deleting the directory `$HOME/fpga-toolchain`

Building pyprofibus PHY-FPGA
----------------------------

To build the PHY-FPGA sources run the following commands:

.. code:: sh

	cd phy_fpga
	make clean
	make
