pyprofibus - PROFIBUS-DP stack
==============================

`https://bues.ch/a/profibus <https://bues.ch/a/profibus>`_

pyprofibus is an Open Source `PROFIBUS-DP <https://en.wikipedia.org/wiki/Profibus>`_ stack written in Python.


Hardware
========

pyprofibus is able to run on any machine that supports Python. It also runs on embedded machines such as the `Raspberry Pi <https://en.wikipedia.org/wiki/Raspberry_Pi>`_ or even tiny microcontrollers such as the `ESP32 <https://en.wikipedia.org/wiki/ESP32>`_ (Micropython).

Please read the hardware documentation for more information:

`pyprofibus hardware documentation <doc/hardware.rst>`_


Speed / Baud rate
=================

The achievable Profibus-DP speed depends on the hardware that it runs on and what kind of serial transceiver is used. There is no software side artificial limit.

Please see the `pyprofibus hardware documentation <doc/hardware.rst>`_


Examples
========

pyprofibus comes with a couple of examples that can teach you how to use pyprofibus in your project.

* Example that runs pyprofibus without any hardware. This example can be used to play around with pyprofibus.
	* examples/example_dummy_oneslave.py
	* examples/example_dummy_oneslave.conf
	* examples/example_dummy_twoslaves.py
	* examples/example_dummy_twoslaves.conf
	* examples/example_dummy_inputonly.py
	* examples/example_dummy_inputonly.conf

* Example that runs pyprofibus as master connected to an ET200S as slave.
	* examples/example_et200s.py
	* examples/example_et200s.conf

* Example that runs pyprofibus as master connected to an S7-315-2DP as *slave*.
	* examples/example_s7-315-2dp.py
	* examples/example_s7-315-2dp.conf


Dependencies
============

* `Python <https://www.python.org/>`_ 3.5 or later.
* Or alternatively `Micropython <https://micropython.org/>`_. Please see the `pyprofibus Micropython help <micropython/README.rst>`_ for more information.


License
=======

Copyright (c) 2013-2022 Michael Buesch <m@bues.ch>

Licensed under the terms of the GNU General Public License version 2, or (at your option) any later version.
