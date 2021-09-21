# -*- coding: utf-8 -*-
#
# PROFIBUS - GSD file parser
#
# Copyright (c) 2016-2021 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus.compat import *

import gc
import re

from pyprofibus.util import ProfibusError
from pyprofibus.gsd.fields import *

__all__ = [
	"GsdError",
	"GsdParser",
]

class GsdError(ProfibusError):
	pass

class GsdParser(object):
	"""GSD file/data parser.
	"""

	class _Line(object):
		"""Raw line.
		"""

		__slots__ = (
			"lineNr",
			"text",
		)

		def __init__(self, lineNr, text):
			self.lineNr = lineNr
			self.text = text

		def __repr__(self):
			return "_Line(lineNr=%d, text='%s')" % (
				self.lineNr, self.text)

	@classmethod
	def fromFile(cls, filepath, debug=False):
		def readfile():
			try:
				with open(filepath, "rb") as fd:
					while True:
						line = fd.readline()
						if not line:
							break
						yield line.decode("latin_1").rstrip("\r\n")
			except (IOError, UnicodeError) as e:
				raise GsdError("Failed to read GSD file '%s':\n%s" % (
					filepath, str(e)))
		return cls(readfile(), filepath, debug)

	@classmethod
	def fromBytes(cls, data, filename=None, debug=False):
		try:
			lines = data.decode("latin_1").splitlines()
		except UnicodeError as e:
			raise GsdError("Failed to parse GSD data: %s" % str(e))
		return cls(lines, filename, debug)

	@classmethod
	def fromPy(cls, moduleName, debug=False):
		try:
			mod = __import__(moduleName)
		except Exception as e:
			raise GsdError("Failed to import GSD Python dump: %s" % str(e))
		return cls(mod.fields, moduleName, debug)

	def __init__(self, lines, filename=None, debug=False):
		self.__debug = debug
		self.__filename = filename
		self.__reset()
		self.__parse(lines)

	def dumpPy(self,
		   stripStr=False,
		   noText=False,
		   noExtUserPrmData=False,
		   modules=None):
		"""Dump the GSD as Python code.
		stripStr: Strip leading and trailing whitespace from strings.
		noText: Discard all PrmText.
		noExtUserPrmData: Discard all ExtUserPrmData and ExtUserPrmDataRef.
		modules: List of modules to include. If None: include all.
		"""
		if modules:
			modules = [ Module.sanitizeName(m) for m in modules ]
		import copy
		def empty(x):
			return not (x is None or
				    (isinstance(x, (dict, list, tuple)) and not x))
		def dup(x):
			if isinstance(x, (tuple, list)):
				return [ dup(a) for a in x if empty(dup(a)) ]
			if isinstance(x, dict):
				return { a : dup(b) for a, b in x.items() if empty(dup(b)) }
			if isinstance(x, str) and stripStr:
				return x.strip()
			if isinstance(x, PrmText) and noText:
				return None
			if isinstance(x, ExtUserPrmData):
				if noExtUserPrmData:
					return None
				y = copy.copy(x)
				y.name = ""
				return y
			if isinstance(x, ExtUserPrmDataRef) and noExtUserPrmData:
				return None
			if isinstance(x, Module):
				if (modules is not None and
				    Module.sanitizeName(x.name) not in modules):
					return None
				y = copy.copy(x)
				y.name = Module.sanitizeName(y.name)
				return y
			return copy.copy(x)
		fields = dup(self.__fields)
		return "from pyprofibus.gsd.fields import "\
		       "GSD_STR, "\
		       "PrmText, "\
		       "PrmTextValue, "\
		       "ExtUserPrmData, "\
		       "ExtUserPrmDataConst, "\
		       "ExtUserPrmDataRef, "\
		       "Module; "\
		       "fields = " + gsdrepr(fields)

	def getFileName(self):
		return self.__filename

	def debugEnabled(self):
		return self.__debug

	def __reset(self):
		self.__fields = {}

	def __preprocess(self, lines):
		lines = [ self._Line(i + 1, l)
			  for i, l in enumerate(lines) ]

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
		gc.collect()

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
		gc.collect()

		# Expand line continuations.
		newLines, inCont = [], False
		for line in lines:
			if inCont:
				if line.text.endswith("\\"):
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
		gc.collect()

		# Strip all lines and remove empty lines.
		newLines = []
		for line in lines:
			line.text = line.text.strip()
			if line.text:
				newLines.append(line)
		lines = newLines
		gc.collect()

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
		return bytes(bytearray(data))

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
				try:
					if offset.strip().startswith("0x"):
						offset = int(offset, 16)
					else:
						offset = int(offset, 10)
				except ValueError as e:
					self.__parseErr(line, "%s invalid" % name)
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
				PrmText(value))
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
					ExtUserPrmData(refNr, name))
				self.__state = self._STATE_EXTUSERPRMDATA
			except ValueError as e:
				self.__parseErr(line, "ExtUserPrmData invalid")
			return
		offset, value = self.__tryByteArray(line, "Ext_User_Prm_Data_Const",
						    hasOffset = True)
		if value is not None:
			self.__fields.setdefault("Ext_User_Prm_Data_Const", []).append(
				ExtUserPrmDataConst(offset, value))
			return
		offset, value = self.__trySimpleNum(line, "Ext_User_Prm_Data_Ref",
						    hasOffset = True)
		if value is not None:
			self.__fields.setdefault("Ext_User_Prm_Data_Ref", []).append(
				ExtUserPrmDataRef(offset, value))
			return
		m = self._reModule.match(line.text)
		if m:
			try:
				name = m.group(1)
				config = m.group(2)
				configBytes = self.__parseByteArray(config)
				self.__fields.setdefault("Module", []).append(
					Module(name, configBytes))
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
			prmText.texts.append(PrmTextValue(offset, value))
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
				extUserPrmData.fields[name] = value
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
				module.fields[name] = value
				return

		# Parse simple booleans.
		for name in ("Preset", ):
			value = self.__trySimpleBool(line, name)
			if value is not None:
				module.fields[name] = value
				return

		# Parse specials
		offset, value = self.__tryByteArray(line, "Ext_User_Prm_Data_Const",
						    hasOffset = True)
		if value is not None:
			module.fields.setdefault("Ext_User_Prm_Data_Const", []).append(
				ExtUserPrmDataConst(offset, value))
			return
		offset, value = self.__trySimpleNum(line, "Ext_User_Prm_Data_Ref",
						    hasOffset = True)
		if value is not None:
			module.fields.setdefault("Ext_User_Prm_Data_Ref", []).append(
				ExtUserPrmDataRef(offset, value))
			return

		self.__parseWarn(line, "Ignored unknown line")

	def __parse(self, lines):
		if isinstance(lines, dict):
			self.__fields = lines
			return

		lines = self.__preprocess(lines)

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
