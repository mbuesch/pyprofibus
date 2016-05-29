"""
#
# PROFIBUS - GSD file interpreter
#
# Copyright (c) 2016 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#
"""

from __future__ import division, absolute_import, print_function, unicode_literals

from pyprofibus.gsd.parser import GsdParser, GsdError

import difflib


class GsdInterp(GsdParser):
	"""GSD file/data interpreter.
	"""

	def __init__(self, text, filename = None, debug = False):
		super(GsdInterp, self).__init__(text, filename, debug)
		self.__configMods = []

	def __interpErr(self, errorText):
		raise GsdError("GSD '%s': %s" % (
			self.getFileName() or "<data>",
			errorText))

	def __interpWarn(self, errorText):
		if not self.__debug:
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

	def setConfiguredModules(self, moduleNameList, force = False):
		"""Set the list of modules plugged into the device.
		"""
		if not self.isModular() and not force:
			self.__interpErr("Trying to configure modules, "
				"but station is non-modular.")
		self.__configMods = []
		for modName in moduleNameList:
			mod = self.findModule(modName)
			if not mod:
				self.__interpErr("Module '%s' not found in GSD." % (
					modName))
			self.__configMods.append(mod)

	def isModular(self):
		"""Returns True, if this is a modular device.
		"""
		return self.getField("Modular_Station", False)

	def getCfgDataElements(self):
		"""Get a tuple of config data elements (DpCfgDataElement)
		for this station with the configured modules.
		"""
		pass#TODO

	def getUserPrmData(self):
		"""Get a bytearray of User_Prm_Data
		for this station with the configured modules.
		"""
		def merge(baseData, extData, offset):
			if extData is not None:
				baseData[offset : len(extData) + offset] = extData
		def trunc(data, length, fieldname, extend = True):
			if length is not None:
				if extend:
					data.extend((0,) * (length - len(data)))
				if len(data) > length:
					self.__interpWarn("User_Prm_Data "
						"truncated by %s" % fieldname)
					data[:] = data[0:length]
		# Get the global data.
		data = self.getField("User_Prm_Data", bytearray())
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
		if self.getField("DPV1_Slave", False):
			pass#TODO modify DPv1 params
		trunc(data, self.getField("Max_User_Prm_Data_Len"),
		      "Max_User_Prm_Data_Len", False)
		return data

	def __str__(self):
		text = []

		vendor = self.getField("Vendor_Name", "")
		model = self.getField("Model_Name", "")
		rev = self.getField("Revision", "")
		ident = self.getField("Ident_Number")
		text.append("%s; %s; %s; Ident: %s\n" % (
			vendor, model, rev,
			("0x%04X" % ident) if ident is not None else "-"))

		order = self.getField("OrderNumber")
		if order:
			text.append("Order number: %s\n" % order)

		for module in self.getField("Module"):
			if module.getField("Preset"):
				continue
			text.append("Available module:  \"%s\"\n" % module.name)

		return "".join(text)
