# pyprofibus hardware documentation

pyprofibus can run on about anything that has a serial port.

However some hardware is superior to other. See the documentation below for the various hardware alternatives and its characteristics.


## pyprofibus on Linux with FPGA PHY

This is the fastest albeit most expensive alternative to connect pyprofibus to a Profibus network. Currently bitrates of up to 1.5 MBaud are supported.

The pyprofibus FPGA is connected via high speed SPI bus to the host computer. It's known to work well with the Raspberry Pi. However it's not strictly limited to that as host computer. The pyprofibus FPGA PHY driver utilizes the Linux SPI subsystem for communication to the FPGA board.

Please see the
[pyprofibus FPGA PHY documentation](hardware_fpga.html)
for more information on how to build and run the FPGA PHY.


## pyprofibus on Linux with /dev/ttyS0 or /dev/ttyAMA0 serial port

Using the Linux serial port is a supported albeit slow alternative to connect pyprofibus to a Profibus network. It only supports low bitrates of up to about 19200 baud (depends on the actual hardware).

Use the pyprofibus configuration as follows to run pyprofibus on serial port:

<pre>
[PHY]
type=serial
dev=/dev/ttyS0
rtscts=False
dsrdtr=False
baud=19200
</pre>


## pyprofibus on Linux with /dev/ttyUSB0 serial port

It is not recommended to run pyprofibus on an emulated USB serial adapter. USB does not meet the realtime requirements of Profibus. It might work at slow bitrates, though. Use without any guarantees.


## pyprofibus on MS Windows

pyprofibus has been reported to work on Windows with the `serial` PHY. Just use the COM1 / COM2 / COMx as `dev=` in the configuration. The same restrictions apply as with Linux `serial` PHY. Please the the Linux /dev/ttyS0 section.
