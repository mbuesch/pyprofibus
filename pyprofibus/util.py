#
# Utility helpers
#
# Copyright (c) 2013 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

import time


class ProfibusError(Exception):
	pass

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


class TimeLimit(object):
	UNLIMITED = -1

	# limit => The time limit, in seconds.
	#          Negative value = unlimited.
	def __init__(self, limit = 0):
		self.__limit = limit
		self.start()

	# (Re-)start the time.
	def start(self, limit = None):
		if limit is not None:
			self.__limit = limit
		self.__startTime = time.time()
		self.__endTime = self.__startTime + self.__limit

	# Add seconds to the limit
	def add(self, seconds):
		self.__limit += seconds
		self.__endTime = self.__startTime + self.__limit

	# Returns True, if the time limit exceed.
	def exceed(self):
		if self.__limit < 0:
			# Unlimited
			return False
		return time.time() >= self.__endTime

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
