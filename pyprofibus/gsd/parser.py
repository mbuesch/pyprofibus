# -*- coding: utf-8 -*-
#
# PROFIBUS - GSD file parser
#
# Copyright (c) 2016 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from __future__ import division, absolute_import, print_function, unicode_literals

import re

from pyprofibus.util import ProfibusError


class GsdError(ProfibusError):
	pass

class GsdParser(object):
	"""GSD file/data parser.
	"""

	class _Line(object):
		"""Raw line.
		"""

		def __init__(self, lineNr, text):
			self.lineNr = lineNr
			self.text = text

		def __repr__(self):
			return "_Line(lineNr = %d, text = '%s')" % (
				self.lineNr, self.text)

	class _Item(object):
		"""Abstract item base class.
		"""

		def __init__(self):
			self._fields = {}

		def getField(self, name, default = None):
			"""Get a field by name.
			"""
			return self._fields.get(name, default)

	class _PrmText(_Item):
		"""PrmText section.
		"""

		def __init__(self, refNr):
			GsdParser._Item.__init__(self)
			self.refNr = refNr
			self.texts = []

	class _PrmTextValue(_Item):
		"""PrmText text value.
		"""

		def __init__(self, offset, text):
			GsdParser._Item.__init__(self)
			self.offset = offset
			self.text = text

	class _ExtUserPrmData(_Item):
		"""ExtUserPrmData section.
		"""

		def __init__(self, refNr, name):
			GsdParser._Item.__init__(self)
			self.refNr = refNr
			self.name = name

	class _ExtUserPrmDataConst(_Item):
		"""Ext_User_Prm_Data_Const(x)
		"""

		def __init__(self, offset, dataBytes):
			GsdParser._Item.__init__(self)
			self.offset = offset
			self.dataBytes = dataBytes

	class _ExtUserPrmDataRef(_Item):
		"""Ext_User_Prm_Data_Ref(x)
		"""

		def __init__(self, offset, refNr):
			GsdParser._Item.__init__(self)
			self.offset = offset
			self.refNr = refNr

	class _Module(_Item):
		"""Module section.
		"""

		def __init__(self, name, configBytes):
			GsdParser._Item.__init__(self)
			self.name = name
			self.configBytes = configBytes

	@classmethod
	def fromFile(cls, filepath, debug = False):
		try:
			with open(filepath, "rb") as fd:
				data = fd.read()
		except (IOError, UnicodeError) as e:
			raise GsdError("Failed to read GSD file '%s':\n%s" % (
				filepath, str(e)))
		return cls.fromBytes(data, filepath, debug)

	@classmethod
	def fromBytes(cls, data, filename = None, debug = False):
		try:
			text = data.decode("latin_1")
		except UnicodeError as e:
			raise GsdError("Failed to parse GSD data: %s" % str(e))
		return cls(text, filename, debug)

	def __init__(self, text, filename = None, debug = False):
		self.__debug = debug
		self.__filename = filename
		self.__reset()
		self.__parse(text)

	def getFileName(self):
		return self.__filename

	def debugEnabled(self):
		return self.__debug

	def __reset(self):
		self.__fields = {}

	def __preprocess(self, text):
		lines = [ self._Line(i + 1, l)
			  for i, l in enumerate(text.splitlines()) ]

		# Find the GSD section and discard the rest.
		newLines, inGsd = [], False
		for line in lines:
			if inGsd:
				if line.text.startswith("#"):
					break
				newLines.append(line)
			else:
				if line.text == "#Profibus_DP":
					inGsd = True
		lines = newLines

		# Remove comments
		newLines = []
		for line in lines:
			newLineText, inQuote = [], False
			for c in line.text:
				if inQuote:
					inQuote = (c == '"')
				else:
					if c == ";":
						line.text = "".join(newLineText)
						line.text = line.text.rstrip()
						break
					inQuote = (c == '"')
				newLineText.append(c)
			newLines.append(line)
		lines = newLines

		# Expand line continuations.
		newLines, inCont = [], False
		for line in lines:
			if inCont:
				if line.text.rstrip().endswith("\\"):
					line.text = line.text[:-1]
				else:
					inCont = False
				newLines[-1].text += line.text
			else:
				if line.text.endswith("\\"):
					line.text = line.text[:-1]
					inCont = True
				newLines.append(line)
		lines = newLines

		# Strip all lines and remove empty lines.
		newLines = []
		for line in lines:
			line.text = line.text.strip()
			if line.text:
				newLines.append(line)
		lines = newLines

		return lines

	_reNum = r'(?:0x[0-9a-fA-F]+)|(?:[0-9]+)'
	_reStr = r'[ a-zA-Z0-9\._\-\+\*\/\<\>\(\)\[\]\{\}\!\$\%\&\?\^\|\=\#\;\,\:\`]+'

	_reExtUserPrmData = re.compile(r'^ExtUserPrmData\s*=\s*(' +\
				       _reNum + r')\s+' +\
				       r'"(' + _reStr + r')"$')
	_reModule = re.compile(r'^Module\s*=\s*' +\
			       r'"(' + _reStr + r')"\s+' +\
			       r'(.+)$')

	_STATE_GLOBAL		= 0
	_STATE_PRMTEXT		= 1
	_STATE_EXTUSERPRMDATA	= 2
	_STATE_MODULE		= 3

	def __parseErr(self, line, errorText):
		raise GsdError("GSD parsing failed in "
			"'%s' at line %d:\n%s\n --> %s" % (
			self.__filename or "GSD data",
			line.lineNr, line.text, errorText))

	def __parseWarn(self, line, errorText):
		if not self.__debug:
			return
		print("GSD parser warning in "
			"'%s' at line %d:\n%s\n --> %s" % (
			self.__filename or "GSD data",
			line.lineNr, line.text, errorText))

	@classmethod
	def __parseNum(cls, numText):
		numText = numText.strip()
		if numText.startswith("0x"):
			return int(numText[2:], 16)
		return int(numText, 10)

	@classmethod
	def __parseByteArray(cls, byteText):
		data = byteText.split(",")
		data = [ cls.__parseNum(d) for d in data ]
		return bytearray(data)

	def __trySimpleNum(self, line, name, hasOffset = False):
		m = re.match(r'^' + name +\
			     ((r'\s*\(\s*(' + self._reNum + r')\s*\)\s*')\
			      if hasOffset else r'\s*') +\
			     r'=\s*(' + self._reNum + r')$',
			     line.text)
		offset, value = None, None
		if m:
			try:
				if hasOffset:
					offset = self.__parseNum(m.group(1))
					value = m.group(2)
				else:
					value = m.group(1)
				value = self.__parseNum(value)
			except ValueError as e:
				self.__parseErr(line, "%s invalid" % name)
		return (offset, value) if hasOffset else value

	def __trySimpleBool(self, line, name):
		value = self.__trySimpleNum(line, name)
		if value is not None:
			return bool(value)
		return None

	def __trySimpleStr(self, line, name, hasOffset = False):
		m = re.match(r'^' + name +\
			     ((r'\s*\(\s*(' + self._reNum + r')\s*\)\s*')\
			      if hasOffset else r'\s*') +\
			     r'=\s*"(' + self._reStr + r')"$',
			     line.text)
		offset, value = None, None
		if m:
			if hasOffset:
				offset = m.group(1)
				value = m.group(2)
			else:
				value = m.group(1)
		return (offset, value) if hasOffset else value

	def __tryStrNoQuotes(self, line, name):
		m = re.match(r'^' + name + r'\s*=\s*(.*)$',
			     line.text)
		if m:
			return m.group(1)
		return None

	def __tryByteArray(self, line, name, hasOffset = False):
		m = re.match(r'^' + name +\
			     ((r'\s*\(\s*(' + self._reNum + r')\s*\)\s*')\
			      if hasOffset else r'\s*') +\
			     r'=\s*(.*)$',
			     line.text)
		offset, data = None, None
		if m:
			try:
				if hasOffset:
					offset = self.__parseNum(m.group(1))
					data = self.__parseByteArray(m.group(2))
				else:
					data = self.__parseByteArray(m.group(1))
			except ValueError as e:
				self.__parseErr(line, "%s invalid" % name)
		return (offset, data) if hasOffset else data

	def __parseLine_global(self, line):
		# Parse simple numbers.
		for name in ("GSD_Revision", "Ident_Number",
			     "Protocol_Ident", "Station_Type",
			     "Repeater_Ctrl_Sig", "24V_Pins",
			     "S7HeaderCnf", "OffsetFirstMPDBlock",
			     "ETERDelay", "MaxResponseDelay",
			     "Min_Slave_Intervall", "Max_Diag_Data_Len",
			     "Modul_Offset", "Max_Module",
			     "Max_Input_Len", "Max_Output_Len",
			     "Max_Data_Len", "MaxTsdr_9.6", "MaxTsdr_19.2",
			     "MaxTsdr_45.45", "MaxTsdr_93.75", "MaxTsdr_187.5",
			     "MaxTsdr_500", "MaxTsdr_1.5M", "MaxTsdr_3M",
			     "MaxTsdr_6M", "MaxTsdr_12M", "User_Prm_Data_Len",
			     "Max_User_Prm_Data_Len"):
			value = self.__trySimpleNum(line, name)
			if value is not None:
				self.__fields[name] = value
				return

		# Parse simple booleans.
		for name in ("Freeze_Mode_supp", "Sync_Mode_supp",
			     "Set_Slave_Add_supp", "Redundancy",
			     "IsActive", "OnlyNormalModules",
			     "DiagBufferable", "Fail_Safe",
			     "Modular_Station", "Auto_Baud_supp",
			     "9.6_supp", "19.2_supp", "45.45_supp",
			     "93.75_supp", "187.5_supp", "500_supp",
			     "1.5M_supp", "3M_supp", "6M_supp",
			     "12M_supp", "FixPresetModules",
			     "DPV1_Slave"):
			value = self.__trySimpleBool(line, name)
			if value is not None:
				self.__fields[name] = value
				return

		# Parse simple strings.
		for name in ("Vendor_Name", "Model_Name",
			     "Revision", "Hardware_Release",
			     "Software_Release", "Implementation_Type",
			     "Bitmap_Device", "Bitmap_SF",
			     "OrderNumber", "Periphery"):
			value = self.__trySimpleStr(line, name)
			if value is not None:
				self.__fields[name] = value
				return

		# Parse specials
		value = self.__trySimpleNum(line, "PrmText")
		if value is not None:
			self.__fields.setdefault("PrmText", []).append(
				self._PrmText(value))
			self.__state = self._STATE_PRMTEXT
			return
		value = self.__tryStrNoQuotes(line, "Slave_Family")
		if value is not None:
			self.__fields["Slave_Family"] = value.split("@")
			return
		value = self.__tryByteArray(line, "User_Prm_Data")
		if value is not None:
			self.__fields["User_Prm_Data"] = value
			return
		m = self._reExtUserPrmData.match(line.text)
		if m:
			try:
				refNr = self.__parseNum(m.group(1))
				name = m.group(2)
				self.__fields.setdefault("ExtUserPrmData", []).append(
					self._ExtUserPrmData(refNr, name))
				self.__state = self._STATE_EXTUSERPRMDATA
			except ValueError as e:
				self.__parseErr(line, "ExtUserPrmData invalid")
			return
		offset, value = self.__tryByteArray(line, "Ext_User_Prm_Data_Const",
						    hasOffset = True)
		if value is not None:
			self.__fields.setdefault("Ext_User_Prm_Data_Const", []).append(
				self._ExtUserPrmDataConst(offset, value))
			return
		offset, value = self.__trySimpleNum(line, "Ext_User_Prm_Data_Ref",
						    hasOffset = True)
		if value is not None:
			self.__fields.setdefault("Ext_User_Prm_Data_Ref", []).append(
				self._ExtUserPrmDataRef(offset, value))
			return
		m = self._reModule.match(line.text)
		if m:
			try:
				name = m.group(1)
				config = m.group(2)
				configBytes = self.__parseByteArray(config)
				self.__fields.setdefault("Module", []).append(
					self._Module(name, configBytes))
				self.__state = self._STATE_MODULE
			except ValueError as e:
				self.__parseErr(line, "Module invalid")
			return

		self.__parseWarn(line, "Ignored unknown line")

	def __parseLine_prmText(self, line):
		if line.text == "EndPrmText":
			self.__state = self._STATE_GLOBAL
			return

		prmText = self.__fields["PrmText"][-1]

		# Parse specials
		offset, value = self.__trySimpleStr(line, "Text",
						    hasOffset = True)
		if value is not None:
			prmText.texts.append(self._PrmTextValue(offset, value))
			return

		self.__parseWarn(line, "Ignored unknown line")

	def __parseLine_extUserPrmData(self, line):
		if line.text == "EndExtUserPrmData":
			self.__state = self._STATE_GLOBAL
			return

		extUserPrmData = self.__fields["ExtUserPrmData"][-1]

		# Parse simple numbers.
		for name in ("Prm_Text_Ref", ):
			value = self.__trySimpleNum(line, name)
			if value is not None:
				extUserPrmData._fields[name] = value
				return

		self.__parseWarn(line, "Ignored unknown line")

	def __parseLine_module(self, line):
		if line.text == "EndModule":
			self.__state = self._STATE_GLOBAL
			return

		module = self.__fields["Module"][-1]

		# Parse simple numbers.
		for name in ("Ext_Module_Prm_Data_Len", ):
			value = self.__trySimpleNum(line, name)
			if value is not None:
				module._fields[name] = value
				return

		# Parse simple booleans.
		for name in ("Preset", ):
			value = self.__trySimpleBool(line, name)
			if value is not None:
				module._fields[name] = value
				return

		# Parse specials
		offset, value = self.__tryByteArray(line, "Ext_User_Prm_Data_Const",
						    hasOffset = True)
		if value is not None:
			module._fields.setdefault("Ext_User_Prm_Data_Const", []).append(
				self._ExtUserPrmDataConst(offset, value))
			return
		offset, value = self.__trySimpleNum(line, "Ext_User_Prm_Data_Ref",
						    hasOffset = True)
		if value is not None:
			module._fields.setdefault("Ext_User_Prm_Data_Ref", []).append(
				self._ExtUserPrmDataRef(offset, value))
			return

		self.__parseWarn(line, "Ignored unknown line")

	def __parse(self, text):
		lines = self.__preprocess(text)

		self.__state = self._STATE_GLOBAL

		for line in lines:
			if self.__state == self._STATE_GLOBAL:
				self.__parseLine_global(line)
			elif self.__state == self._STATE_PRMTEXT:
				self.__parseLine_prmText(line)
			elif self.__state == self._STATE_EXTUSERPRMDATA:
				self.__parseLine_extUserPrmData(line)
			elif self.__state == self._STATE_MODULE:
				self.__parseLine_module(line)
			else:
				assert(0)

	def getField(self, name, default = None):
		"""Get a field by name.
		"""
		return self.__fields.get(name, default)
