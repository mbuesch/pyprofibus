#!/usr/bin/env python3

from __future__ import print_function

from distutils.core import setup
from pyprofibus.version import VERSION_STRING


setup(	name		= "pyprofibus",
	version		= VERSION_STRING,
	description	= "Python PROFIBUS module",
	license		= "GNU General Public License v2 or later",
	author		= "Michael Buesch",
	author_email	= "m@bues.ch",
	url		= "https://bues.ch/a/profibus",
	scripts		= [ "gsdparser",
			    "profisniff",
			    "pyprofibus-linuxcnc-hal", ],
	packages	= [ "pyprofibus", "pyprofibus.gsd" ],
	keywords	= [ "PROFIBUS", "PROFIBUS-DP", "SPS", "PLC",
			    "Step 7", "Siemens",
			    "GSD", "GSD parser", "General Station Description", ],
	classifiers	= [
		"Development Status :: 4 - Beta",
		"Environment :: Console",
		"Intended Audience :: Developers",
		"Intended Audience :: Education",
		"Intended Audience :: Information Technology",
		"Intended Audience :: Manufacturing",
		"Intended Audience :: Science/Research",
		"License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
		"Operating System :: POSIX",
		"Operating System :: POSIX :: Linux",
#		"Programming Language :: Cython",
		"Programming Language :: Python",
		"Programming Language :: Python :: 2.7",
		"Programming Language :: Python :: 3",
		"Programming Language :: Python :: Implementation :: CPython",
		"Programming Language :: Python :: Implementation :: PyPy",
#		"Programming Language :: Python :: Implementation :: Jython",
#		"Programming Language :: Python :: Implementation :: IronPython",
		"Topic :: Education",
		"Topic :: Home Automation",
		"Topic :: Scientific/Engineering",
		"Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator",
		"Topic :: Software Development :: Embedded Systems",
		"Topic :: System :: Hardware",
		"Topic :: System :: Hardware :: Hardware Drivers",
		"Topic :: System :: Networking",
	],
	long_description = open("README.md").read()
)
