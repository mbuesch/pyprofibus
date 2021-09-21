# -*- coding: utf-8 -*-
#
# PROFIBUS - GSD file interpreter
#
# Copyright (c) 2016-2021 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus.compat import *

from pyprofibus.gsd.parser import GsdParser, GsdError
from pyprofibus.dp import DpCfgDataElement

import difflib

__all__ = [
	"GsdInterp",
]

class GsdInterp(GsdParser):
	"""GSD file/data interpreter.
	"""

	def __init__(self, text, filename=None, debug=False):
		super(GsdInterp, self).__init__(text, filename, debug)
		self.__configMods = []
		self.__addPresetModules(onlyFixed=False)
		if not self.isModular():
			self.__addAllModules()

	def __interpErr(self, errorText):
		raise GsdError("GSD '%s': %s" % (
			self.getFileName() or "<data>",
			errorText))

	def __interpWarn(self, errorText):
		if not self.debugEnabled():
			return
		print("Warning in GSD '%s': %s" % (
			self.getFileName() or "<data>",
			errorText))

	@staticmethod
	def __findInSequence(sequence, findName, getItemName):
		if not sequence:
			return None
		nameLower = findName.lower().strip()

		# Check if there's only one matching exactly.
		matches = [ item for item in sequence
			    if findName == getItemName(item) ]
		if len(matches) == 1:
			return matches[0]

		# Check if there's only one matching exactly (case insensitive).
		matches = [ item for item in sequence
			    if nameLower == getItemName(item).lower().strip() ]
		if len(matches) == 1:
			return matches[0]

		# Check if there's only one matching at the start.
		matches = [ item for item in sequence
			    if getItemName(item).lower().strip().startswith(nameLower) ]
		if len(matches) == 1:
			return matches[0]

		# Fuzzy match.
		matches = difflib.get_close_matches(
				findName,
				( getItemName(item) for item in sequence ),
				n = 1)
		if matches:
			matches = [ item for item in sequence
				    if getItemName(item) == matches[0] ]
			if matches:
				return matches[0]
		return None

	def findModule(self, name):
		"""Find a module by name.
		Returns a _Module instance, if found. None otherwise.
		"""
		return self.__findInSequence(self.getField("Module"),
					     name,
					     lambda module: module.name)

	def __addPresetModules(self, onlyFixed=False):
		if not self.getField("FixPresetModules", False) and\
		   onlyFixed:
			return
		for mod in self.getField("Module", []):
			if mod.getField("Preset", False):
				self.__configMods.append(mod)

	def __addAllModules(self):
		"""Configure all available modules as plugged into the device.
		"""
		for mod in self.getField("Module", []):
			if not mod.getField("Preset", False):
				self.__configMods.append(mod)

	def clearConfiguredModules(self):
		"""Remove all configured modules.
		This also removes all preset modules, except for the fixed preset mods.
		"""
		self.__configMods = []
		self.__addPresetModules(onlyFixed=True)

	def setConfiguredModule(self, moduleName, index=-1):
		"""Set a configured module that is plugged into the device.
		If index>=0 then set the module at the specified index.
		If index<0 then append the module.
		If moduleName is None then the module is removed.
		"""
		if index >= 0 and index < len(self.__configMods) and\
		   self.getField("FixPresetModules", False) and\
		   self.__configMods[index].getField("Preset", False):
			self.__interpErr("Not modifying fixed preset module "
				"at index %d." % index)
		if moduleName is None:
			if index >= 0 and index < len(self.__configMods):
				self.__configMods.pop(index)
			else:
				self.__interpErr("Module index %d out of range." % (
					index))
		else:
			mod = self.findModule(moduleName)
			if not mod:
				self.__interpErr("Module '%s' not found in GSD." % (
					moduleName))
			if index < 0 or index >= len(self.__configMods):
				self.__configMods.append(mod)
			else:
				self.__configMods[index] = mod

	def isModular(self):
		"""Returns True, if this is a modular device.
		"""
		return self.getField("Modular_Station", False)

	def isDPV1(self):
		"""Returns True, if this is a DPV1 slave.
		"""
		return self.getField("DPV1_Slave", False)

	def getCfgDataElements(self):
		"""Get a tuple of config data elements (DpCfgDataElement)
		for this station with the configured modules.
		"""
		elems = []
		for mod in self.__configMods:
			elems.append(DpCfgDataElement(
				mod.configBytes[0],
				mod.configBytes[1:]))
		return elems

	def getUserPrmData(self, dp1PrmMask = None, dp1PrmSet = None):
		"""Get a bytearray of User_Prm_Data
		for this station with the configured modules.
		dp1PrmMask/Set: Optional mask/set override for the DPV1 prm.
		"""
		def merge(baseData, extData, offset):
			if extData is not None:
				baseData[offset : len(extData) + offset] = extData
		def trunc(data, length, fieldname, extend = True):
			if length is not None:
				if extend:
					data.extend(bytearray(max(length - len(data), 0)))
				if len(data) > length:
					self.__interpWarn("User_Prm_Data "
						"truncated by %s" % fieldname)
					data[:] = data[0:length]
		# Get the global data.
		data = bytearray(self.getField("User_Prm_Data", b""))
		trunc(data, self.getField("User_Prm_Data_Len"),
		      "User_Prm_Data_Len")
		for dataConst in self.getField("Ext_User_Prm_Data_Const", []):
			merge(data, dataConst.dataBytes, dataConst.offset)
		# Append the module parameter data.
		for mod in self.__configMods:
			modData = bytearray()
			for dataConst in mod.getField("Ext_User_Prm_Data_Const", []):
				merge(modData, dataConst.dataBytes, dataConst.offset)
			trunc(modData, mod.getField("Ext_Module_Prm_Data_Len"),
			      "Ext_Module_Prm_Data_Len")
			# Add to global data.
			data += modData
		if self.isDPV1():
			assert((dp1PrmMask is None and dp1PrmSet is None) or\
			       (dp1PrmMask is not None and dp1PrmSet is not None))
			if dp1PrmMask is not None:
				assert(len(dp1PrmMask) == 3 and len(dp1PrmSet) == 3)
				if len(data) < 3:
					self.__interpErr("DPv1 User_Prm_Data is "
						"shorter than 3 bytes.")
				# Apply the DPv1 prm override.
				for i in range(3):
					data[i] = (data[i] & ~dp1PrmMask[i]) |\
						  (dp1PrmSet[i] & dp1PrmMask[i])
		elif dp1PrmMask is not None:
			self.__interpWarn("DPv1 User_Prm_Data override ignored")
		trunc(data, self.getField("Max_User_Prm_Data_Len"),
		      "Max_User_Prm_Data_Len", False)
		return bytes(data)

	def getIdentNumber(self):
		"""Get the ident number.
		"""
		ident = self.getField("Ident_Number")
		if ident is None:
			self.__interpErr("No Ident_Number in GSD.")
		return ident

	def getMaxTSDR(self, baudrate):
		"""Get the max-tSDR.
		Might return None.
		"""
		baud2fieldname = {
			9600		: "MaxTsdr_9.6",
			19200		: "MaxTsdr_19.2",
			45450		: "MaxTsdr_45.45",
			93750		: "MaxTsdr_93.75",
			187500		: "MaxTsdr_187.5",
			500000		: "MaxTsdr_500",
			1500000		: "MaxTsdr_1.5M",
			3000000		: "MaxTsdr_3M",
			6000000		: "MaxTsdr_6M",
			12000000	: "MaxTsdr_12M",
		}
		if baudrate not in baud2fieldname:
			self.__interpErr("getMaxTSDR: Invalid baud rate.")
		fieldname = baud2fieldname[baudrate]
		return self.getField(fieldname, None)

	def __str__(self):
		text = []

		if self.getFileName():
			text.append("File:              %s\n" %\
				    self.getFileName())
		vendor = self.getField("Vendor_Name", "")
		model = self.getField("Model_Name", "")
		rev = self.getField("Revision", "")
		ident = self.getField("Ident_Number")
		text.append("Device:            %s; %s; %s; Ident %s\n" % (
			vendor, model, rev,
			("0x%04X" % ident) if ident is not None else "-"))

		order = self.getField("OrderNumber")
		if order:
			text.append("Order number:      %s\n" % order)

		for module in self.getField("Module", []):
			if module.getField("Preset"):
				continue
			text.append("Available module:  \"%s\"\n" % module.name)

		return "".join(text)
