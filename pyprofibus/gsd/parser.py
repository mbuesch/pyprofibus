"""
#
# PROFIBUS - GSD file parser
#
# Copyright (c) 2016 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#
"""

from __future__ import division, absolute_import, print_function, unicode_literals

import re

from pyprofibus.util import ProfibusError


class GsdError(ProfibusError):
	pass

class GsdParser(object):
	"""GSD file/data parser.
	"""

	_baudrates = (("9.6", 9600),
		      ("19.2", 19200),
		      ("45.45", 45450),
		      ("93.75", 93750),
		      ("187.5", 187500),
		      ("500", 500000),
		      ("1.5M", 1500000),
		      ("3M", 3000000),
		      ("6M", 6000000),
		      ("12M", 12000000))

	class _Line(object):
		"""Raw line.
		"""

		def __init__(self, lineNr, text):
			self.lineNr = lineNr
			self.text = text

		def __repr__(self):
			return "_Line(lineNr = %d, text = '%s')" % (
				self.lineNr, self.text)

	class _PrmText(object):
		"""PrmText section.
		"""

		def __init__(self, refNr):
			self.refNr = refNr
			self.texts = []

	class _ExtUserPrmData(object):
		"""ExtUserPrmData section.
		"""

		def __init__(self, refNr, name):
			self.refNr = refNr
			self.name = name

	class _ExtUserPrmDataConst(object):
		"""Ext_User_Prm_Data_Const(x)
		"""

		def __init__(self, offset, dataBytes):
			self.offset = offset
			self.dataBytes = dataBytes

	class _ExtUserPrmDataRef(object):
		"""Ext_User_Prm_Data_Ref(x)
		"""

		def __init__(self, offset, refNr):
			self.offset = offset
			self.refNr = refNr

	class _Module(object):
		"""Module section.
		"""

		def __init__(self, name, configBytes):
			self.name = name
			self.configBytes = configBytes
			self.preset = None

	@classmethod
	def fromFile(cls, filepath):
		try:
			with open(filepath, "rb") as fd:
				data = fd.read()
		except (IOError, UnicodeError) as e:
			raise GsdError("Failed to read GSD file '%s':\n%s" % (
				filepath, str(e)))
		return cls.fromBytes(data)

	@classmethod
	def fromBytes(cls, data):
		try:
			text = data.decode("latin_1")
		except UnicodeError as e:
			raise GsdError("Failed to parse GSD data: %s" % str(e))
		return cls(text)

	def __init__(self, text):
		self.__reset()
		self.__parse(text)

	def __reset(self):
		self.__gsdRevision = None
		self.__vendorName = None
		self.__modelName = None
		self.__revision = None
		self.__identNumber = None
		self.__slaveFamily = None
		self.__protocolIdent = None
		self.__stationType = None
		self.__hardwareRelease = None
		self.__softwareRelease = None
		self.__autoBaudSupp = None
		self.__baudSupp = {}
		self.__maxTsdr = {}
		for baudStr, baud in self._baudrates:
			self.__baudSupp[baud] = None
			self.__maxTsdr[baud] = None
		self.__redundancy = None
		self.__repeaterCtrlSig = None
		self.__prmText = []
		self.__extUserPrmData = []
		self.__24vPins = None
		self.__implementationType = None
		self.__bitmapDevice = None
		self.__bitmapSF = None
		self.__orderNumber = None
		self.__periphery = None
		self.__s7HeaderCnf = None
		self.__isActive = None
		self.__onlyNormalModules = None
		self.__diagBufferable = None
		self.__offsetFirstMPDBlock = None
		self.__ETERDelay = None
		self.__maxResponseDelay = None
		self.__failSafe = None
		self.__minSlaveIntervall = None
		self.__maxDiagDataLen = None
		self.__modulOffset = None
		self.__modularStation = None
		self.__maxModule = None
		self.__maxInputLen = None
		self.__maxOutputLen = None
		self.__maxDataLen = None
		self.__userPrmDataLen = None
		self.__maxUserPrmDataLen = None
		self.__userPrmData = None
		self.__extUserPrmDataConst = []
		self.__extUserPrmDataRef = []
		self.__fixPresetModules = None
		self.__module = []

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

		# Expand line continuations.
		newLines, inCont = [], False
		for line in lines:
			if inCont:
				newLines[-1].text += line.text
			else:
				newLines.append(line)
			inCont = line.text.endswith("\\")
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
						break
					inQuote = (c == '"')
				newLineText.append(c)
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
		raise GsdError("GSD parsing failed at "
			"line %d:\n%s\n --> %s" % (
			line.lineNr, line.text, errorText))

	def __parseWarn(self, line, errorText):
		print("GSD parser warning at "
			"line %d:\n%s\n --> %s" % (
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

	def __trySimpleStr(self, line, name):
		m = re.match(r'^' + name + r'\s*=\s*"(' + self._reStr + r')"$',
			     line.text)
		if m:
			return m.group(1)
		return None

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
		value = self.__trySimpleNum(line, "GSD_Revision")
		if value is not None:
			self.__gsdRevision = value
			return
		value = self.__trySimpleNum(line, "PrmText")
		if value is not None:
			self.__prmText.append(self._PrmText(value))
			self.__state = self._STATE_PRMTEXT
			return
		value = self.__trySimpleStr(line, "Vendor_Name")
		if value is not None:
			self.__vendorName = value
			return
		value = self.__trySimpleStr(line, "Model_Name")
		if value is not None:
			self.__modelName = value
			return
		value = self.__trySimpleStr(line, "Revision")
		if value is not None:
			self.__revision = value
			return
		value = self.__trySimpleNum(line, "Ident_Number")
		if value is not None:
			self.__identNumber = value
			return
		value = self.__tryStrNoQuotes(line, "Slave_Family")
		if value is not None:
			self.__slaveFamily = value.split("@")
			return
		value = self.__trySimpleNum(line, "Protocol_Ident")
		if value is not None:
			self.__protocolIdent = value
			return
		value = self.__trySimpleNum(line, "Station_Type")
		if value is not None:
			self.__stationType = value
			return
		value = self.__trySimpleStr(line, "Hardware_Release")
		if value is not None:
			self.__hardwareRelease = value
			return
		value = self.__trySimpleStr(line, "Software_Release")
		if value is not None:
			self.__softwareRelease = value
			return
		value = self.__trySimpleBool(line, "Redundancy")
		if value is not None:
			self.__redundancy = value
			return
		value = self.__trySimpleNum(line, "Repeater_Ctrl_Sig")
		if value is not None:
			self.__repeaterCtrlSig = value
			return
		value = self.__trySimpleNum(line, "24V_Pins")
		if value is not None:
			self.__24vPins = value
			return
		value = self.__trySimpleStr(line, "Implementation_Type")
		if value is not None:
			self.__implementationType = value
			return
		value = self.__trySimpleStr(line, "Bitmap_Device")
		if value is not None:
			self.__bitmapDevice = value
			return
		value = self.__trySimpleStr(line, "Bitmap_SF")
		if value is not None:
			self.__bitmapSF = value
			return
		value = self.__trySimpleStr(line, "OrderNumber")
		if value is not None:
			self.__orderNumber = value
			return
		value = self.__trySimpleStr(line, "Periphery")
		if value is not None:
			self.__periphery = value
			return
		value = self.__trySimpleNum(line, "S7HeaderCnf")
		if value is not None:
			self.__s7HeaderCnf = value
			return
		value = self.__trySimpleBool(line, "IsActive")
		if value is not None:
			self.__isActive = value
			return
		value = self.__trySimpleBool(line, "OnlyNormalModules")
		if value is not None:
			self.__onlyNormalModules = value
			return
		value = self.__trySimpleBool(line, "DiagBufferable")
		if value is not None:
			self.__diagBufferable = value
			return
		value = self.__trySimpleNum(line, "OffsetFirstMPDBlock")
		if value is not None:
			self.__offsetFirstMPDBlock = value
			return
		value = self.__trySimpleNum(line, "ETERDelay")
		if value is not None:
			self.__ETERDelay = value
			return
		value = self.__trySimpleNum(line, "MaxResponseDelay")
		if value is not None:
			self.__maxResponseDelay = value
			return
		value = self.__trySimpleBool(line, "Fail_Safe")
		if value is not None:
			self.__failSafe = value
			return
		value = self.__trySimpleNum(line, "Min_Slave_Intervall")
		if value is not None:
			self.__minSlaveIntervall = value
			return
		value = self.__trySimpleNum(line, "Max_Diag_Data_Len")
		if value is not None:
			self.__maxDiagDataLen = value
			return
		value = self.__trySimpleNum(line, "Modul_Offset")
		if value is not None:
			self.__modulOffset = value
			return
		value = self.__trySimpleBool(line, "Modular_Station")
		if value is not None:
			self.__modularStation = value
			return
		value = self.__trySimpleNum(line, "Max_Module")
		if value is not None:
			self.__maxModule = value
			return
		value = self.__trySimpleNum(line, "Max_Input_Len")
		if value is not None:
			self.__maxInputLen = value
			return
		value = self.__trySimpleNum(line, "Max_Output_Len")
		if value is not None:
			self.__maxOutputLen = value
			return
		value = self.__trySimpleNum(line, "Max_Data_Len")
		if value is not None:
			self.__maxDataLen = value
			return
		value = self.__trySimpleNum(line, "Auto_Baud_supp")
		if value is not None:
			self.__autoBaudSupp = value
			return
		for baudStr, baud in self._baudrates:
			value = self.__trySimpleBool(line, "%s_supp" % baudStr)
			if value is not None:
				self.__baudSupp[baud] = value
				return
			value = self.__trySimpleNum(line, "MaxTsdr_%s" % baudStr)
			if value is not None:
				self.__maxTsdr[baud] = value
				return
		value = self.__trySimpleNum(line, "User_Prm_Data_Len")
		if value is not None:
			self.__userPrmDataLen = value
			return
		value = self.__trySimpleNum(line, "Max_User_Prm_Data_Len")
		if value is not None:
			self.__maxUserPrmDataLen = value
			return
		value = self.__tryByteArray(line, "User_Prm_Data")
		if value is not None:
			self.__userPrmData = value
			return
		m = self._reExtUserPrmData.match(line.text)
		if m:
			try:
				refNr = self.__parseNum(m.group(1))
				name = m.group(2)
				self.__extUserPrmData.append(
					self._ExtUserPrmData(refNr, name))
				self.__state = self._STATE_EXTUSERPRMDATA
			except ValueError as e:
				self.__parseErr(line, "ExtUserPrmData invalid")
			return
		offset, value = self.__tryByteArray(line, "Ext_User_Prm_Data_Const",
						    hasOffset = True)
		if value is not None:
			self.__extUserPrmDataConst.append(
				self._ExtUserPrmDataConst(offset, value))
			return
		offset, value = self.__trySimpleNum(line, "Ext_User_Prm_Data_Ref",
						    hasOffset = True)
		if value is not None:
			self.__extUserPrmDataRef.append(
				self._ExtUserPrmDataRef(offset, value))
			return
		value = self.__trySimpleBool(line, "FixPresetModules")
		if value is not None:
			self.__fixPresetModules = value
			return
		m = self._reModule.match(line.text)
		if m:
			try:
				name = m.group(1)
				config = m.group(2)
				configBytes = self.__parseByteArray(config)
				self.__module.append(
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
		pass#TODO

		self.__parseWarn(line, "Ignored unknown line")

	def __parseLine_extUserPrmData(self, line):
		if line.text == "EndExtUserPrmData":
			self.__state = self._STATE_GLOBAL
			return
		pass#TODO

		self.__parseWarn(line, "Ignored unknown line")

	def __parseLine_module(self, line):
		if line.text == "EndModule":
			self.__state = self._STATE_GLOBAL
			return
		pass#TODO

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
