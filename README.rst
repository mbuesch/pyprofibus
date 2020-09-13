pyprofibus - PROFIBUS-DP stack
==============================

`https://bues.ch/a/profibus <https://bues.ch/a/profibus>`_

pyprofibus is an Open Source `PROFIBUS-DP <https://en.wikipedia.org/wiki/Profibus>`_ stack written in Python.


Hardware
========

pyprofibus is able to run on any machine that supports Python. It also runs on embedded machines such as the `Raspberry Pi <https://en.wikipedia.org/wiki/Raspberry_Pi>`_ or even tiny microcontrollers such as the `ESP32 <https://en.wikipedia.org/wiki/ESP32>`_ (Micropython).

Please read the hardware documentation for more information:

`pyprofibus hardware documentation <doc/hardware.html>`_


Speed / Baud rate
=================

The achievable Profibus-DP speed depends on the hardware that it runs on and what kind of serial transceiver is used. There is no software side artificial limit.

Please see the `pyprofibus hardware documentation <doc/hardware.html>`_


Examples
========

pyprofibus comes with a couple of examples that can teach you how to use pyprofibus in your project.

* Example that runs pyprofibus without any hardware. This example can be used to play around with pyprofibus.
	* example_dummy.py
	* example_dummy.conf

* Example that runs pyprofibus as master connected to an ET200S as slave.
	* example_et200s.py
	* example_et200s.conf

* Example that runs pyprofibus as master connected to an S7-315-2DP as *slave*.
	* example_s7-315-2dp.py
	* example_s7-315-2dp.conf


Dependencies
============

* `Python <https://www.python.org/>`_ 3.4 or later.
* Or alternatively `Micropython <https://micropython.org/>`_. Please see the `pyprofibus Micropython help <micropython/README.html>`_ for more information.


License
=======

Copyright (c) 2013-2020 Michael Buesch <m@bues.ch>

Licensed under the terms of the GNU General Public License version 2, or (at your option) any later version.
