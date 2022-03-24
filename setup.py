#!/usr/bin/env python3

from __future__ import print_function

import sys, os
basedir = os.path.abspath(os.path.dirname(__file__))

for base in (os.getcwd(), basedir):
	sys.path.insert(0, os.path.join(base, "misc"))
	# Add the basedir to PYTHONPATH before we try to import pyprofibus.version
	sys.path.insert(0, base)

from setuptools import setup
import setup_cython
import warnings
import re
from pyprofibus.version import VERSION_STRING


isWindows = os.name.lower() in {"nt", "ce"}
isPosix = os.name.lower() == "posix"


def getEnvInt(name, default = 0):
	try:
		return int(os.getenv(name, "%d" % default))
	except ValueError:
		return default

def getEnvBool(name, default = False):
	return bool(getEnvInt(name, 1 if default else 0))

buildCython = getEnvInt("PYPROFIBUS_CYTHON_BUILD", 3 if isPosix else 0)
buildCython = ((buildCython == 1) or (buildCython == sys.version_info[0]))
setup_cython.parallelBuild = bool(getEnvInt("PYPROFIBUS_CYTHON_PARALLEL", 1) == 1 or\
				  getEnvInt("PYPROFIBUS_CYTHON_PARALLEL", 1) == sys.version_info[0])
setup_cython.profileEnabled = bool(getEnvInt("PYPROFIBUS_PROFILE") > 0)
setup_cython.debugEnabled = bool(getEnvInt("PYPROFIBUS_DEBUG_BUILD") > 0)

def pyCythonPatchLine(line):
	# Patch the import statements
	line = re.sub(r'^(\s*from pyprofibus[0-9a-zA-Z_]*)\.([0-9a-zA-Z_\.]+) import', r'\1_cython.\2 import', line)
	line = re.sub(r'^(\s*from pyprofibus[0-9a-zA-Z_]*)\.([0-9a-zA-Z_\.]+) cimport', r'\1_cython.\2 cimport', line)
	line = re.sub(r'^(\s*import pyprofibus[0-9a-zA-Z_]*)\.', r'\1_cython.', line)
	line = re.sub(r'^(\s*cimport pyprofibus[0-9a-zA-Z_]*)\.', r'\1_cython.', line)
	return line

setup_cython.pyCythonPatchLine = pyCythonPatchLine

cmdclass = {}

# Try to build the Cython modules. This might fail.
if buildCython:
	buildCython = setup_cython.cythonBuildPossible()
if buildCython:
	cmdclass["build_ext"] = setup_cython.CythonBuildExtension
	setup_cython.registerCythonModules()
else:
	print("Skipping build of CYTHON modules.")

ext_modules = setup_cython.ext_modules


warnings.filterwarnings("ignore", r".*'long_description_content_type'.*")

with open(os.path.join(basedir, "README.rst"), "rb") as fd:
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
	packages	= [ "pyprofibus", "pyprofibus.gsd", "pyprofibus.phy_fpga_driver" ],
	cmdclass	= cmdclass,
	ext_modules	= ext_modules,
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
		"Programming Language :: Cython",
		"Programming Language :: Python",
		"Programming Language :: Python :: 3",
		"Programming Language :: Python :: Implementation :: CPython",
		"Programming Language :: Python :: Implementation :: PyPy",
		"Programming Language :: Python :: Implementation :: MicroPython",
		"Topic :: Education",
		"Topic :: Home Automation",
		"Topic :: Scientific/Engineering",
		"Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator",
		"Topic :: Scientific/Engineering :: Human Machine Interfaces",
		"Topic :: Software Development :: Embedded Systems",
		"Topic :: Software Development :: Libraries",
		"Topic :: System :: Hardware",
		"Topic :: System :: Hardware :: Hardware Drivers",
		"Topic :: System :: Networking",
	],
	long_description=readmeText,
	long_description_content_type="text/x-rst",
)
