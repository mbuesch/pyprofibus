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


class TimeLimited(object):
	# limit => The time limit, in seconds.
	#          Negative value = unlimited.
	def __init__(self, limit):
		self.__limit = limit
		self.start()

	# (Re-)start the time.
	def start(self):
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

	# Sleep for 'seconds'.
	@classmethod
	def sleep(cls, seconds=0.001):
		time.sleep(seconds)
