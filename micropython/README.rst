pyprofibus Micropython support
==============================

This directory contains scripts and support files for pyprofibus on `Micropython <https://micropython.org/>`_.


Installing pyprofibus on a Micropython device
=============================================

Run the install.sh script to build and install pyprofibus to a Micropython device via USB-UART.

Run `install.sh -h` for more help.

`install.sh` prepares and cross-compiles all pyprofibus files for the target platform to optimize resource usage.

Example
-------

Your device is an ESP32 (xtensawin) connected to the computer as /dev/ttyUSB0.
Two GSD modules are configured in your pyprofibus .conf file. For example:

* 6ES7 138-4CA01-0AA0 PM-E DC24V
* 6ES7 132-4BB30-0AA0  2DO DC24V

The corresponding command to build and install pyprofibus is:

.. code:: sh

	./micropython/install.sh --march xtensawin --module "6ES7 138-4CA01-0AA0 PM-E DC24V" --module "6ES7 132-4BB30-0AA0  2DO DC24V" /dev/ttyUSB0

Prerequisites
=============

The following tools have to be available on your Linux compatible system to build pyprofibus for Micropython:

* The latest version of Micropython has to be installed on your device. See `these instructions <https://micropython.org/download/esp32/>`_ for installing Micropython on an ESP32 device.
* `mpy-cross`: `Micropython cross compiler <https://github.com/micropython/micropython>`_.
* `pyboard.py`: Device flashing script `from Micropython distribution <https://github.com/micropython/micropython/blob/master/tools/pyboard.py>`_ to copy pyprofibus to the device.
* `make`: `GNU make <https://www.gnu.org/software/make/>`_.

These tools must be available in your PATH.

You may pass the parameters `--pyboard` and/or `--mpycross` to `install.sh` to specify the path to your tool installation location.


Resource usage
==============

pyprofibus requires a fair amount of memory to run.

Currently about 100 kBytes of memory available to the Micropython Garbage Collector are required to run pyprofibus. The more memory is available, the better. Remember that your application code also has to run in addition to pyprofibus.

You can check the memory available to the GC with the following commands:

.. code:: python

	import micropython
	micropython.mem_info()


Supported devices
=================

pyprofibus has been tested on:

* ESP32 WROOM32

pyprofibus probably runs on other devices, too. The major limiting factor is the memory available to pyprofibus.


main.py
=======

Please see the file `main.py` and edit it to your needs.

It is the main file that will be executed after boot. It should start your application and pyprofibus.


boot.py
=======

The script `boot.py` sets up a basic environment after Micropython boot. You probably don't need to edit the default `boot.py` script shipped with pyprofibus.
