pyprofibus hardware documentation
=================================

pyprofibus can run on about anything that has a serial port.

However some hardware is superior to other. See the documentation below for the various hardware alternatives and its characteristics.


pyprofibus on Linux with /dev/ttyS0 or /dev/ttyAMA0 serial port
===============================================================

Using the Linux serial port is a supported way to connect pyprofibus to a Profibus network. On some boards it may only supports low baud rates of up to about 19200 baud. However that depends on the actual serial transceiver hardware. On certain embedded boards with flexible serial hardware, high baudrates such as 1.5 MBaud may also be possible.

To run pyprofibus on serial port configure pyprofibus as follows:

.. code:: ini

	[PHY]
	type=serial
	dev=/dev/ttyS0
	baud=19200

pyprofibus on Linux with /dev/ttyUSB0 serial port
=================================================

It is not recommended to run pyprofibus on an emulated USB serial adapter. USB does not meet the realtime requirements of Profibus. It might work with slow baud rates, though. Use without any guarantee.


pyprofibus on ESP32 with Micropython
====================================

Pyprofibus on ESP32 with Micropython supports baud rates of at least 1.5 MBaud.

Please see the `pyprofibus Micropython help <../micropython/README.rst>`_.

To run pyprofibus on Micropython serial port (UART 2) configure pyprofibus as follows:

.. code:: ini

	[PHY]
	type=serial
	dev=UART2
	baud=1500000


pyprofibus on Linux with FPGA PHY
=================================

This is one of the fastest albeit most expensive alternative to connect pyprofibus to a Profibus network. Currently baud rates of up to 1.5 MBaud are supported. There is room for improvement towards higher baud rates.

The pyprofibus FPGA is connected via high speed SPI bus to the host computer. It's known to work well with the Raspberry Pi. However it's not strictly limited to that as host computer. The pyprofibus FPGA PHY driver utilizes the Linux SPI subsystem for communication to the FPGA board.

Please see the `pyprofibus FPGA PHY documentation <hardware_fpga.rst>`_ for more information on how to build and run the FPGA PHY.

To run pyprofibus on FPGA PHY configure pyprofibus as follows:

.. code:: ini

	[PHY]
	type=fpga
	spiBus=0
	spiCS=0
	spiSpeedHz=2500000
	baud=1500000

The FPGA PHY is currently not supported on Micropython.


pyprofibus on MS Windows
========================

pyprofibus has been reported to work on Windows with the `serial` PHY. Just use the COM1 / COM2 / COMx as `dev=` in the configuration. The same restrictions apply as with Linux `serial` PHY. Please the the Linux /dev/ttyS0 section.
