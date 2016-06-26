# -*- coding: utf-8 -*-
#
# PROFIBUS DP - Configuration file parser
#
# Copyright (c) 2016 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus.compat import *

from pyprofibus.gsd.interp import GsdInterp
from pyprofibus.gsd.parser import GsdError
from pyprofibus.util import *

import re
from io import StringIO

if isPy2Compat:
	from ConfigParser import SafeConfigParser as _ConfigParser
	from ConfigParser import Error as _ConfigParserError
else:
	from configparser import ConfigParser as _ConfigParser
	from configparser import Error as _ConfigParserError


class PbConfError(ProfibusError):
	pass

class PbConf(object):
	"""Pyprofibus configuration file parser.
	"""

	class _SlaveConf(object):
		"""Slave configuration.
		"""
		addr		= None
		gsd		= None
		syncMode	= None
		freezeMode	= None
		groupMask	= None
		watchdogMs	= None
		inputSize	= None
		outputSize	= None

	# [PROFIBUS] section
	debug		= None
	# [PHY] section
	phyType		= None
	phyDev		= None
	phyBaud		= None
	# [DP] section
	dpMasterClass	= None
	dpMasterAddr	= None
	# [SLAVE_xxx] sections
	slaveConfs	= None

	@classmethod
	def fromFile(cls, filename):
		try:
			with open(filename, "rb") as fd:
				data = fd.read().decode("UTF-8")
		except (IOError, UnicodeError) as e:
			raise PbConfError("Failed to read '%s': %s" %\
				(filename, str(e)))
		return cls(data, filename)

	__reSlave = re.compile(r'^SLAVE_(\d+)$')
	__reMod = re.compile(r'^module_(\d+)$')

	def __init__(self, text, filename = None):
		def get(section, option, fallback = None):
			if p.has_option(section, option):
				return p.get(section, option)
			if fallback is None:
				raise ValueError("Option [%s] '%s' does not exist." % (
					section, option))
			return fallback
		def getboolean(section, option, fallback = None):
			if p.has_option(section, option):
				return p.getboolean(section, option)
			if fallback is None:
				raise ValueError("Option [%s] '%s' does not exist." % (
					section, option))
			return fallback
		def getint(section, option, fallback = None):
			if p.has_option(section, option):
				return p.getint(section, option)
			if fallback is None:
				raise ValueError("Option [%s] '%s' does not exist." % (
					section, option))
			return fallback
		try:
			p = _ConfigParser()
			p.readfp(StringIO(text), filename)

			# [PROFIBUS]
			self.debug = getint("PROFIBUS", "debug",
					    fallback = 0)

			# [PHY]
			self.phyType = get("PHY", "type",
					   fallback = "serial")
			self.phyDev = get("PHY", "dev",
					  fallback = "/dev/ttyS0")
			self.phyBaud = getint("PHY", "baud",
					      fallback = 9600)

			# [DP]
			self.dpMasterClass = getint("DP", "master_class",
						    fallback = 1)
			if self.dpMasterClass not in {1, 2}:
				raise ValueError("Invalid master_class")
			self.dpMasterAddr = getint("DP", "master_addr",
						   fallback = 0x02)
			if self.dpMasterAddr < 0 or self.dpMasterAddr > 127:
				raise ValueError("Invalid master_addr")

			self.slaveConfs = []
			for section in p.sections():
				m = self.__reSlave.match(section)
				if not m:
					continue
				s = self._SlaveConf()
				s.addr = getint(section, "addr")
				s.gsd = GsdInterp.fromFile(
					get(section, "gsd"))
				s.syncMode = getboolean(section, "sync_mode",
							fallback = False)
				s.freezeMode = getboolean(section, "freeze_mode",
							  fallback = False)
				s.groupMask = getboolean(section, "group_mask",
							 fallback = 1)
				if s.groupMask < 0 or s.groupMask > 0xFF:
					raise ValueError("Invalid group_mask")
				s.watchdogMs = getint(section, "watchdog_ms",
						      fallback = 5000)
				if s.watchdogMs < 0 or s.watchdogMs > 255 * 255:
					raise ValueError("Invalid watchdog_ms")
				s.inputSize = getint(section, "input_size")
				if s.inputSize < 0 or s.inputSize > 246:
					raise ValueError("Invalid input_size")
				s.outputSize = getint(section, "output_size")
				if s.outputSize < 0 or s.outputSize > 246:
					raise ValueError("Invalid output_size")

				mods = [ o for o in p.options(section)
					 if self.__reMod.match(o) ]
				mods.sort(key = lambda o: self.__reMod.match(o).group(1))
				for option in mods:
					s.gsd.setConfiguredModule(get(section, option))

				self.slaveConfs.append(s)

		except (_ConfigParserError, ValueError) as e:
			raise PbConfError("Profibus config file parse "
				"error:\n%s" % str(e))
		except GsdError as e:
			raise PbConfError("Failed to parse GSD file:\n%s" % str(e))

	def makePhy(self):
		"""Create a CP-PHY instance based on the configuration.
		"""
		phyType = self.phyType.lower().strip()
		if phyType == "serial":
			import pyprofibus.phy_serial
			phy = pyprofibus.phy_serial.CpPhySerial(
				debug = (self.debug >= 2),
				port = self.phyDev)
		elif phyType in {"dummyslave", "dummy_slave", "dummy-slave"}:
			import pyprofibus.phy_dummy
			phy = pyprofibus.phy_dummy.CpPhyDummySlave(
				debug = (self.debug >= 2))
		else:
			raise PbConfError("Invalid phyType parameter value: "
					  "%s" % self.phyType)
		phy.setConfig(baudrate = self.phyBaud)
		return phy
