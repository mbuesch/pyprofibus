# -*- coding: utf-8 -*-
#
# Utility helpers
#
# Copyright (c) 2013-2020 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus.compat import *

import os
import time
import errno

__all__ = [
	"ProfibusError",
	"bytesToHex",
	"intToHex",
	"boolToStr",
	"fileExists",
	"monotonic_time",
	"TimeLimit",
	"FaultDebouncer",
]

class ProfibusError(Exception):
	__slots__ = (
	)

def bytesToHex(b, sep=" "):
	if b is None:
		return "None"
	assert isinstance(b, (bytes, bytearray))
	if not b:
		return "Empty"
	return sep.join("%02X" % c for c in bytearray(b))

def intToHex(val):
	if val is None:
		return "None"
	assert isinstance(val, int)
	val &= 0xFFFFFFFF
	if val <= 0xFF:
		return "0x%02X" % val
	elif val <= 0xFFFF:
		return "0x%04X" % val
	elif val <= 0xFFFFFF:
		return "0x%06X" % val
	else:
		return "0x%08X" % val

def boolToStr(val):
	return str(bool(val))

def fileExists(filename):
	"""Returns True, if the file exists.
	Returns False, if the file does not exist.
	Returns None, if another error occurred.
	"""
	try:
		os.stat(filename)
	except OSError as e:
		if e.errno == errno.ENOENT:
			return False
		return None
	return True

# Monotonic time. Returns a float second count.
if isMicropython:
	def monotonic_time():
		return time.ticks_ms() / 1e3
else:
	monotonic_time = getattr(time, "monotonic", time.time)

class TimeLimit(object):
	"""Generic timeout helper.
	"""

	UNLIMITED	= -1	# No limit

	__slots__ = (
		"__limit",
		"__startTime",
		"__endTime",
	)

	# limit => The time limit, in seconds.
	#          Negative value = unlimited.
	def __init__(self, limit = 0):
		self.__limit = limit
		self.start()

	# (Re-)start the time.
	def start(self, limit = None):
		if limit is None:
			limit = self.__limit
		self.__limit = limit
		if limit >= 0:
			self.__startTime = monotonic_time()
			self.__endTime = self.__startTime + limit
		else:
			self.__startTime = self.__endTime = -1

	# Add seconds to the limit
	def add(self, seconds):
		if self.__limit >= 0:
			self.__limit += seconds
			self.__endTime = self.__startTime + self.__limit

	# Returns True, if the time limit exceed.
	def exceed(self):
		if self.__limit < 0:
			return False	# Unlimited
		return monotonic_time() >= self.__endTime

class FaultDebouncer(object):
	"""Fault counter/debouncer.
	"""

	__slots__ = (
		"__countMax",
		"__count",
	)

	def __init__(self, countMax = 0xFFFF):
		self.__countMax = countMax
		self.reset()

	def reset(self):
		self.__count = 0

	def inc(self):
		if self.__count < self.__countMax - 2:
			self.__count += 2
		return (self.__count + 1) // 2

	def dec(self):
		if self.__count > 0:
			self.__count -= 1
		return (self.__count + 1) // 2

	fault = inc
	ok = dec

	def get(self):
		return (self.__count + 1) // 2
