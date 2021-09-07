# -*- coding: utf-8 -*-
#
# PROFIBUS DP - Communication Processor PHY access library
#
# Copyright (c) 2013-2021 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus.compat import *

import time
import sys
from collections import deque

from pyprofibus.util import *


__all__ = [
	"PhyError",
	"CpPhy",
]


class PhyError(ProfibusError):
	"""PHY exception.
	"""

class CpPhy(object):
	"""PROFIBUS CP PHYsical layer base class.
	"""

	PFX = "PHY: "

	# Profibus baud-rates
	BAUD_9600	= 9600
	BAUD_19200	= 19200
	BAUD_45450	= 45450
	BAUD_93750	= 93750
	BAUD_187500	= 187500
	BAUD_500000	= 500000
	BAUD_1500000	= 1500000
	BAUD_3000000	= 3000000
	BAUD_6000000	= 6000000
	BAUD_12000000	= 12000000

	__slots__ = (
		"debug",
		"__txQueueDAs",
		"__txQueueTelegrams",
		"__allocUntil",
		"__secPerFrame",
	)

	def __init__(self, debug=False, *args, **kwargs):
		self.debug = debug
		self.__close()

	def _debugMsg(self, msg):
		if self.debug:
			print(self.PFX + str(msg))

	def _warningMsg(self, msg):
		print("%sWarning: %s" % (self.PFX, str(msg)))

	def close(self):
		"""Close the PHY device.
		This method may be reimplemented in the PHY driver.
		"""
		self.__close()

	def __close(self):
		self.__txQueueDAs = deque()
		self.__txQueueTelegrams = [None] * (0x7F + 1)
		self.__allocUntil = monotonic_time()
		self.__secPerFrame = 0.0

	def sendData(self, telegramData, srd):
		"""Send data to the physical line.
		Reimplement this method in the PHY driver.
		"""
		raise NotImplementedError

	def pollData(self, timeout):
		"""Poll received data from the physical line.
		timeout => timeout in seconds.
			   0.0 = no timeout, return immediately.
			   negative = unlimited.
		Reimplement this method in the PHY driver.
		"""
		raise NotImplementedError

	def poll(self, timeout=0.0):
		"""timeout => timeout in seconds.
			      0.0 = no timeout, return immediately.
			      negative = unlimited.
		"""
		if self.__txQueueDAs:
			self.__send()
		return self.pollData(timeout)

	def __send(self):
		now = monotonic_time()
		if self.__canAllocateBus(now):
			da = self.__txQueueDAs.popleft()
			telegram, srd, maxReplyLen = self.__txQueueTelegrams[da]
			self.__txQueueTelegrams[da] = None
			telegramData = telegram.getRawData()
			self.__allocateBus(now, len(telegramData), maxReplyLen)
			self.sendData(telegramData, srd)

	def send(self, telegram, srd, maxReplyLen=-1):
		if maxReplyLen < 0 or maxReplyLen > 255:
			maxReplyLen = 255

		da = telegram.da
		if self.__txQueueTelegrams[da] is None:
			self.__txQueueDAs.append(da)
		self.__txQueueTelegrams[da] = (telegram, srd, maxReplyLen)

		self.__send()

	def setConfig(self, baudrate=BAUD_9600, *args, **kwargs):
		"""Set the PHY configuration.
		This method may be reimplemented in the PHY driver.
		"""
		symLen = 1.0 / baudrate
		self.__secPerFrame = symLen * float(1 + 8 + 1 + 1)

	def __canAllocateBus(self, now):
		return now >= self.__allocUntil

	def __allocateBus(self, now, nrSendOctets, nrReplyOctets):
		secPerFrame = self.__secPerFrame
		seconds = secPerFrame * nrSendOctets
		if nrReplyOctets:
			pass#TODO IFS
			seconds += secPerFrame * nrReplyOctets
		pass#TODO
		self.__allocUntil = now + seconds

	def releaseBus(self):
		self.__allocUntil = monotonic_time()
		if self.__txQueueDAs:
			self.__send()

	def clearTxQueueAddr(self, da):
		"""Remove all TX queue entries for the given destination address.
		"""
		if da in self.__txQueueDAs:
			self.__txQueueDAs.remove(da)
		self.__txQueueTelegrams[da] = None
