#!/usr/bin/env python3

from __future__ import print_function

import sys, os
basedir = os.path.abspath(os.path.dirname(__file__))

# Add the basedir to PYTHONPATH before we try to import pyprofibus.version
sys.path.insert(0, os.getcwd())
sys.path.insert(0, basedir)

from pyprofibus.version import VERSION_STRING
from distutils.core import setup
import warnings


warnings.filterwarnings("ignore", r".*'long_description_content_type'.*")

with open(os.path.join(basedir, "README.md"), "rb") as fd:
	readmeText = fd.read().decode("UTF-8")

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
		"Topic :: Education",
		"Topic :: Home Automation",
		"Topic :: Scientific/Engineering",
		"Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator",
		"Topic :: Software Development :: Embedded Systems",
		"Topic :: System :: Hardware",
		"Topic :: System :: Hardware :: Hardware Drivers",
		"Topic :: System :: Networking",
	],
	long_description=readmeText,
	long_description_content_type="text/markdown",
)
