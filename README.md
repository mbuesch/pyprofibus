# pyprofibus - PROFIBUS-DP stack

pyprofibus is a [PROFIBUS-DP](https://en.wikipedia.org/wiki/Profibus)
stack written in Python.


## Hardware

What hardware can pyprofibus be run on? Please read the hardware documentation for more information:

[pyprofibus hardware documentation](doc/hardware.html)


## Examples

pyprofibus comes with a couple of examples that can teach you how to use pyprofibus in your project.

<table>

<tr>
<td>
<pre>
example_dummy.py
example_dummy.conf
</pre>
</td>
<td>
Example that runs pyprofibus without any hardware.<br />
This example can be used to play around with pyprofibus.
</td>
</tr>

<tr>
<td>
<pre>
example_et200s.py
example_et200s.conf
</pre>
</td>
<td>
Example that runs pyprofibus as master connected to an ET&nbsp;200S as slave.
</td>
</tr>

<tr>
<td>
<pre>
example_s7-315-2dp.py
example_s7-315-2dp.conf
</pre>
</td>
<td>
Example that runs pyprofibus as master connected to an S7-315-2DP as <u>slave</u>.
</td>
</tr>

</table>


## Dependencies

* Python 3.4 or later or Python 2.7: [python.org](https://www.python.org/)


## License

Copyright (c) 2013-2019 Michael Buesch <m@bues.ch>

Licensed under the terms of the GNU General Public License version 2,
or (at your option) any later version.
