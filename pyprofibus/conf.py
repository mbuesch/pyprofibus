# -*- coding: utf-8 -*-
#
# PROFIBUS DP - Configuration file parser
#
# Copyright (c) 2016-2021 Michael Buesch <m@bues.ch>
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
import sys
from io import StringIO

if isPy2Compat:
	from ConfigParser import SafeConfigParser as _ConfigParser
	from ConfigParser import Error as _ConfigParserError
else:
	from configparser import ConfigParser as _ConfigParser
	from configparser import Error as _ConfigParserError

__all__ = [
	"PbConfError",
	"PbConf",
]

def loadGsd(name, debug=0):
	exceptions = []
	# Try name as a direct file name.
	try:
		return GsdInterp.fromFile(name, debug=(debug > 0))
	except GsdError as e:
		exceptions.append(str(e))
	# Try to interpret the name as a module name.
	try:
		if "/" not in name:
			mod = name.replace(".gsd", "_gsd")
			return GsdInterp.fromPy(mod, debug=(debug > 0))
	except GsdError as e:
		exceptions.append(str(e))
	# Try to interpret the name as a module name with leading fs path components stripped.
	try:
		slashIdx = name.rfind("/")
		if slashIdx >= 0:
			mod = name[slashIdx + 1 : ].replace(".gsd", "_gsd")
			return GsdInterp.fromPy(mod, debug=(debug > 0))
	except GsdError as e:
		exceptions.append(str(e))
	raise GsdError("\n".join(exceptions))

class PbConfError(ProfibusError):
	pass

class PbConf(object):
	"""Pyprofibus configuration file parser.
	"""

	class _SlaveConf(object):
		"""Slave configuration.
		"""
		index		= None
		name		= None
		addr		= None
		gsd		= None
		syncMode	= None
		freezeMode	= None
		groupMask	= None
		watchdogMs	= None
		inputSize	= None
		outputSize	= None
		diagPeriod	= None

		def makeDpSlaveDesc(self):
			"""Create a DpSlaveDesc instance based on the configuration.
			"""
			from pyprofibus.dp_master import DpSlaveDesc
			slaveDesc = DpSlaveDesc(self)

			# Create Chk_Cfg telegram
			slaveDesc.setCfgDataElements(self.gsd.getCfgDataElements())

			# Set User_Prm_Data
			slaveDesc.setUserPrmData(self.gsd.getUserPrmData())

			# Set various standard parameters
			slaveDesc.setSyncMode(self.syncMode)
			slaveDesc.setFreezeMode(self.freezeMode)
			slaveDesc.setGroupMask(self.groupMask)
			slaveDesc.setWatchdog(self.watchdogMs)

			return slaveDesc

	# [PROFIBUS] section
	debug		= None
	# [PHY] section
	phyType		= None
	phyDev		= None
	phyBaud		= None
	phyRtsCts	= None
	phyDsrDtr	= None
	phySpiBus	= None
	phySpiCS	= None
	phySpiSpeedHz	= None
	# [DP] section
	dpMasterClass	= None
	dpMasterAddr	= None
	# [SLAVE_xxx] sections
	slaveConfs	= None

	@classmethod
	def fromFile(cls, filename):
		if isPy2Compat:
			with open(filename, "r") as fd:
				return cls(fd, filename)
		else:
			with open(filename, "r", encoding="UTF-8") as fd:
				return cls(fd, filename)

	__reSlave = re.compile(r'^SLAVE_(\d+)$')
	__reMod = re.compile(r'^module_(\d+)$')

	def __init__(self, fd, filename=None):
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
			if hasattr(p, "read_file"):
				p.read_file(fd, filename)
			else:
				p.readfp(fd, filename)

			# [PROFIBUS]
			self.debug = getint("PROFIBUS", "debug",
					    fallback=0)

			# [PHY]
			self.phyType = get("PHY", "type",
					   fallback="serial")
			self.phyDev = get("PHY", "dev",
					  fallback="/dev/ttyS0")
			self.phyBaud = getint("PHY", "baud",
					      fallback=9600)
			self.phyRtsCts = getboolean("PHY", "rtscts",
						    fallback=False)
			self.phyDsrDtr = getboolean("PHY", "dsrdtr",
						    fallback=False)
			self.phySpiBus = getint("PHY", "spiBus",
						fallback=0)
			self.phySpiCS = getint("PHY", "spiCS",
					       fallback=0)
			self.phySpiSpeedHz = getint("PHY", "spiSpeedHz",
						    fallback=1000000)

			# [DP]
			self.dpMasterClass = getint("DP", "master_class",
						    fallback=1)
			if self.dpMasterClass not in {1, 2}:
				raise ValueError("Invalid master_class")
			self.dpMasterAddr = getint("DP", "master_addr",
						   fallback=0x02)
			if self.dpMasterAddr < 0 or self.dpMasterAddr > 127:
				raise ValueError("Invalid master_addr")

			self.slaveConfs = []
			for section in p.sections():
				m = self.__reSlave.match(section)
				if not m:
					continue
				index = int(m.group(1))
				s = self._SlaveConf()
				s.index = index
				s.name = get(section, "name", section)
				s.addr = getint(section, "addr")
				s.gsd = loadGsd(get(section, "gsd"), self.debug)
				s.syncMode = getboolean(section, "sync_mode",
							fallback=False)
				s.freezeMode = getboolean(section, "freeze_mode",
							  fallback=False)
				s.groupMask = getboolean(section, "group_mask",
							 fallback=1)
				if s.groupMask < 0 or s.groupMask > 0xFF:
					raise ValueError("Invalid group_mask")
				s.watchdogMs = getint(section, "watchdog_ms",
						      fallback=5000)
				if s.watchdogMs < 0 or s.watchdogMs > 255 * 255:
					raise ValueError("Invalid watchdog_ms")
				s.inputSize = getint(section, "input_size")
				if s.inputSize < 0 or s.inputSize > 246:
					raise ValueError("Invalid input_size")
				s.outputSize = getint(section, "output_size")
				if s.outputSize < 0 or s.outputSize > 246:
					raise ValueError("Invalid output_size")
				s.diagPeriod = getint(section, "diag_period", 0)
				if s.diagPeriod < 0 or s.diagPeriod > 0x3FFFFFFF:
					raise ValueError("Invalid diag_period")

				mods = [ o for o in p.options(section)
					 if self.__reMod.match(o) ]
				mods.sort(key = lambda o: int(self.__reMod.match(o).group(1)))
				if s.gsd.isModular():
					for option in mods:
						s.gsd.setConfiguredModule(get(section, option))
				elif mods:
					print("Warning: Some modules are specified in the config file, "
					      "but the station is 'Compact': Modular_Station=0.",
					      file=sys.stderr)

				self.slaveConfs.append(s)

		except (IOError, UnicodeError) as e:
			raise PbConfError("Failed to read '%s': %s" %\
				(filename, str(e)))
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
			phyClass = pyprofibus.phy_serial.CpPhySerial
			extraKwArgs = {}
		elif phyType in {"dummyslave", "dummy_slave", "dummy-slave"}:
			import pyprofibus.phy_dummy
			phyClass = pyprofibus.phy_dummy.CpPhyDummySlave
			extraKwArgs = {
				"echoDX"	: all(slaveConf.outputSize > 0
						      for slaveConf in self.slaveConfs),
				"echoDXSize"	: max(slaveConf.outputSize
						      for slaveConf in self.slaveConfs),
			}
		elif phyType == "fpga":
			import pyprofibus.phy_fpga
			phyClass = pyprofibus.phy_fpga.CpPhyFPGA
			extraKwArgs = {}
		else:
			raise PbConfError("Invalid phyType parameter value: "
					  "%s" % self.phyType)
		phy = phyClass(debug=(self.debug >= 2),
			       port=self.phyDev,
			       spiBus=self.phySpiBus,
			       spiCS=self.phySpiCS,
			       spiSpeedHz=self.phySpiSpeedHz,
			       **extraKwArgs)
		phy.setConfig(baudrate=self.phyBaud,
			      rtscts=self.phyRtsCts,
			      dsrdtr=self.phyDsrDtr)
		return phy

	def makeDPM(self, phy=None):
		"""Create a DpMaster and a CP-PHY instance based on the configuration.
		Returns the DpMaster instance.
		"""
		if phy is None:
			# Create a PHY (layer 1) interface object.
			phy = self.makePhy()

		# Create a DP class 1 or 2 master.
		from pyprofibus.dp_master import DPM1, DPM2
		if self.dpMasterClass == 1:
			DpMasterClass = DPM1
		elif self.dpMasterClass == 2:
			DpMasterClass = DPM2
		else:
			raise PbConfError("Invalid dpMasterClass parameter value: "
					  "%d" % self.dpMasterClass)
		master = DpMasterClass(phy=phy,
				       masterAddr=self.dpMasterAddr,
				       debug=(self.debug >= 1))
		return master
