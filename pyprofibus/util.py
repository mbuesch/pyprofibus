# -*- coding: utf-8 -*-
#
# Utility helpers
#
# Copyright (c) 2013-2016 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

import os
import time
import errno


class ProfibusError(Exception):
	pass

def bytesToHex(b, sep = " "):
	return sep.join("%02X" % c for c in bytearray(b))

def intToHex(val):
	if val is None:
		return "None"
	val &= 0xFFFFFFFF
	if val <= 0xFF:
		return "0x%02X" % val
	elif val <= 0xFFFF:
		return "0x%04X" % val
	elif val <= 0xFFFFFF:
		return "0x%06X" % val
	else:
		return "0x%08X" % val

def intListToHex(valList):
	if valList is None:
		return "None"
	return "[%s]" % ", ".join(intToHex(b) for b in valList)

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
monotonic_time = getattr(time, "monotonic", time.clock)

class TimeLimit(object):
	"""Generic timeout helper.
	"""

	UNLIMITED	= -1	# No limit
	DEFAULT		= -2

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
	faultless = dec

	def get(self):
		return (self.__count + 1) // 2
