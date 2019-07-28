# -*- coding: utf-8 -*-
#
# PROFIBUS DP - Bus timing
#
# Copyright (c) 2019 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus.compat import *


class PBTiming(object):
	"""PROFIBUS timing.

	DP master     !    transmission    ! DP slave
	              !                    !
	---- tSYN ---->--------tS/R-------->---------v
	|                                            |
	^----tID1-----<--------tA/R--------<---tSDR---

	"""

	__slots__ = (
		"baud",
		"tBit",
		"tSYN",
		"tQUI",
		"tSET",
		"tSM",
		"minTSDR",
		"tSDI",
		"tID1",
		"tID2",
		"tTD",
	)

	def __init__(self, baud, tSDI, maxTSDR):
		"""Initialize the bus timing object.
		baud is the baud rate of the bus.
		tSDI is the Initiator delay, in bit times.
		maxTSDR is the MaxTsdr_xxx value (in bit times) from gsd of the slave.
		"""

		# Baud rate.
		self.baud = baud

		# Time per bit, in seconds.
		self.tBit = 1.0 / baud

		# Profibus sync time.
		# Bus idle time before a station may start transmission.
		self.tSYN = 33 * self.tBit

		# Quiet time. Line state uncertainty time.
		self.tQUI = 0.33 * self.tBit

		# Line setup time.
		self.tSET = 1 * self.tBit

		# Safety margin.
		self.tSM = (2 * self.tBit) + (2 * self.tSET) + self.tQUI

		# Station delay of responder.
		self.minTSDR = 1 * self.tBit
		self.maxTSDR = maxTSDR * self.tBit

		# Station delay of initiator.
		self.tSDI = tSDI * self.tBit

		# Initiator idle time.
		self.tID1 = max(self.tSYN + self.tSM,
				self.minTSDR,
				self.tSDI)

		# Initiator idle time after frames which are not to be acked.
		self.tID2 = max(self.tSYN + self.tSM,
				self.maxTSDR)

		# Transmission delay time between sender and receiver.
		self.tTD = 0.33 * self.tBit

	def tSR(self, nrTxOctets):
		"""Frame transmission time for send/request.
		"""
		return nrTxOctets * 11 * self.tBit

	def tAR(self, nrRxOctets):
		"""Frame transmission time for ACK/response.
		"""
		return nrRxOctets * 11 * self.tBit

	def tMC(self, nrTxOctets, nrRxOctets):
		"""Message cycle time.
		"""
		return self.tSR(nrTxOctets) + self.maxTSDR + self.tAR(nrRxOctets) + self.tID1 + (2 * self.tTD)

	def tMC_noACK(self, nrTxOctets):
		"""Message cycle time.
		"""
		return self.tSR(nrTxOctets) + self.maxTSDR + self.tID2 + (2 * self.tTD)
