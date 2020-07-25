# -*- coding: utf-8 -*-
#
# PROFIBUS - GSD file parser
#
# Copyright (c) 2016-2020 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

import re

__all__ = [
	"GSD_STR",
	"gsdrepr",
	"PrmText",
	"PrmTextValue",
	"ExtUserPrmData",
	"ExtUserPrmDataConst",
	"ExtUserPrmDataRef",
	"Module",
]

GSD_STR = (
	"Prm_Text_Ref",
	"Ext_Module_Prm_Data_Len",
	"ExtUserPrmData",
	"Ext_User_Prm_Data_Const",
	"Ext_User_Prm_Data_Ref",
)

def gsdrepr(x):
	if isinstance(x, list):
		return "[%s]" % ", ".join(gsdrepr(a) for a in x)
	if isinstance(x, tuple):
		return "(%s, )" % ", ".join(gsdrepr(a) for a in x)
	if isinstance(x, dict):
		return "{%s}" % ", ".join("%s : %s\n" % (gsdrepr(a), gsdrepr(b))
					  for a, b in x.items())
	if isinstance(x, str):
		for i, cs in enumerate(GSD_STR):
			if cs == x:
				return "GSD_STR[%s]" % i
	return repr(x)

class _Item(object):
	"""Abstract item base class.
	"""

	__slots__ = (
		"fields",
	)

	def __init__(self, fields=None):
		self.fields = fields or {}

	def getField(self, name, default=None):
		"""Get a field by name.
		"""
		return self.fields.get(name, default)

	def _repr_field(self, pfx=", ", sfx=""):
		if self.fields:
			return "%sfields=%s%s" % (pfx, gsdrepr(self.fields), sfx)
		return ""

class PrmText(_Item):
	"""PrmText section.
	"""

	REPR_NAME = "PrmText"

	__slots__ = (
		"refNr",
		"texts",
	)

	def __init__(self, refNr, texts=None, **kwargs):
		_Item.__init__(self, **kwargs)
		self.refNr = refNr
		self.texts = texts or []

	def __repr__(self):
		return "%s(%s, %s%s)" % (
			self.REPR_NAME,
			gsdrepr(self.refNr),
			gsdrepr(self.texts),
			self._repr_field())

class PrmTextValue(_Item):
	"""PrmText text value.
	"""

	REPR_NAME = "PrmTextValue"

	__slots__ = (
		"offset",
		"text",
	)

	def __init__(self, offset, text, **kwargs):
		_Item.__init__(self, **kwargs)
		self.offset = offset
		self.text = text

	def __repr__(self):
		return "%s(%s, %s%s)" % (
			self.REPR_NAME,
			gsdrepr(self.offset),
			gsdrepr(self.text),
			self._repr_field())

class ExtUserPrmData(_Item):
	"""ExtUserPrmData section.
	"""

	REPR_NAME = "ExtUserPrmData"

	__slots__ = (
		"refNr",
		"name",
	)

	def __init__(self, refNr, name, **kwargs):
		_Item.__init__(self, **kwargs)
		self.refNr = refNr
		self.name = name

	def __repr__(self):
		return "%s(%s, %s%s)" % (
			self.REPR_NAME,
			gsdrepr(self.refNr),
			gsdrepr(self.name),
			self._repr_field())

class ExtUserPrmDataConst(_Item):
	"""Ext_User_Prm_Data_Const(x)
	"""

	REPR_NAME = "ExtUserPrmDataConst"

	__slots__ = (
		"offset",
		"dataBytes",
	)

	def __init__(self, offset, dataBytes, **kwargs):
		_Item.__init__(self, **kwargs)
		self.offset = offset
		self.dataBytes = dataBytes

	def __repr__(self):
		return "%s(%s, %s%s)" % (
			self.REPR_NAME,
			gsdrepr(self.offset),
			gsdrepr(self.dataBytes),
			self._repr_field())

class ExtUserPrmDataRef(_Item):
	"""Ext_User_Prm_Data_Ref(x)
	"""

	REPR_NAME = "ExtUserPrmDataRef"

	__slots__ = (
		"offset",
		"refNr",
	)

	def __init__(self, offset, refNr, **kwargs):
		_Item.__init__(self, **kwargs)
		self.offset = offset
		self.refNr = refNr

	def __repr__(self):
		return "%s(%s, %s%s)" % (
			self.REPR_NAME,
			gsdrepr(self.offset),
			gsdrepr(self.refNr),
			self._repr_field())

class Module(_Item):
	"""Module section.
	"""

	REPR_NAME = "Module"

	__slots__ = (
		"name",
		"configBytes",
	)

	@classmethod
	def sanitizeName(cls, name):
		return re.subn(r"\s+", " ", name)[0].strip()

	def __init__(self, name, configBytes, **kwargs):
		_Item.__init__(self, **kwargs)
		self.name = name
		self.configBytes = configBytes

	def __repr__(self):
		return "%s(%s, %s%s)" % (
			self.REPR_NAME,
			gsdrepr(self.name),
			gsdrepr(self.configBytes),
			self._repr_field())
