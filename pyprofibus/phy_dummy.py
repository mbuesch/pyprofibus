# -*- coding: utf-8 -*-
#
# PROFIBUS DP - Communication Processor PHY access library
#
# Copyright (c) 2016-2021 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus.compat import *

from pyprofibus.phy import *
from pyprofibus.fdl import *
from pyprofibus.dp import *
from pyprofibus.util import *

__all__ = [
	"CpPhyDummySlave",
]

class CpPhyDummySlave(CpPhy):
	"""Dummy slave PROFIBUS CP PHYsical layer
	"""

	__slots__ = (
		"__echoDX",
		"__echoDXSize",
		"__pollQueue",
	)

	def __init__(self, *args, **kwargs):
		super(CpPhyDummySlave, self).__init__(*args, **kwargs)
		self.__echoDX = kwargs.get("echoDX", True)
		self.__echoDXSize = kwargs.get("echoDXSize", None)
		self.__pollQueue = []

	def __msg(self, message):
		if self.debug:
			print("CpPhyDummySlave: %s" % message)

	def close(self):
		"""Close the PHY device.
		"""
		self.__pollQueue = []
		super(CpPhyDummySlave, self).close()

	def sendData(self, telegramData, srd):
		"""Send data to the physical line.
		"""
		telegramData = bytearray(telegramData)
		self.__msg("Sending %s  %s" % ("SRD" if srd else "SDN",
					       bytesToHex(telegramData)))
		self.__mockSend(telegramData, srd = srd)

	def pollData(self, timeout=0.0):
		"""Poll received data from the physical line.
		timeout => timeout in seconds.
			   0.0 = no timeout, return immediately.
			   negative = unlimited.
		"""
		try:
			telegramData = self.__pollQueue.pop(0)
		except IndexError as e:
			return None
		self.__msg("Receiving    %s" % bytesToHex(telegramData))
		return telegramData

	def setConfig(self, baudrate=CpPhy.BAUD_9600, *args, **kwargs):
		self.__msg("Baudrate = %d" % baudrate)
		self.__pollQueue = []
		super(CpPhyDummySlave, self).setConfig(baudrate=baudrate, *args, **kwargs)

	def __mockSend(self, telegramData, srd):
		if not srd:
			return
		try:
			fdl = FdlTelegram.fromRawData(telegramData)

			if (fdl.fc & FdlTelegram.FC_REQFUNC_MASK) == FdlTelegram.FC_FDL_STAT:
				telegram = FdlTelegram_FdlStat_Con(da = fdl.sa,
								   sa = fdl.da)
				self.__pollQueue.append(telegram.getRawData())
				return

			dp = DpTelegram.fromFdlTelegram(fdl, thisIsMaster = False)

			if DpTelegram_SlaveDiag_Req.checkType(dp):
				telegram = DpTelegram_SlaveDiag_Con(da = fdl.sa,
								    sa = fdl.da)
				telegram.b1 |= DpTelegram_SlaveDiag_Con.B1_ONE
				self.__pollQueue.append(telegram.toFdlTelegram().getRawData())
				return
			if DpTelegram_SetPrm_Req.checkType(dp):
				telegram = FdlTelegram_ack()
				self.__pollQueue.append(telegram.getRawData())
				return
			if DpTelegram_ChkCfg_Req.checkType(dp):
				telegram = FdlTelegram_ack()
				self.__pollQueue.append(telegram.getRawData())
				return
			if DpTelegram_DataExchange_Req.checkType(dp):
				if self.__echoDX:
					du = bytearray([ d ^ 0xFF for d in dp.du ])
					if self.__echoDXSize is not None:
						if len(du) > self.__echoDXSize:
							du = du[ : self.__echoDXSize]
						if len(du) < self.__echoDXSize:
							du += bytearray(self.__echoDXSize - len(du))
					telegram = DpTelegram_DataExchange_Con(da = fdl.sa,
									       sa = fdl.da,
									       du = du)
					self.__pollQueue.append(telegram.toFdlTelegram().getRawData())
				else:
					telegram = FdlTelegram_ack()
					self.__pollQueue.append(telegram.getRawData())
				return

			self.__msg("Dropping SRD telegram: %s" % str(fdl))
		except ProfibusError as e:
			text = "SRD mock-send error: %s" % str(e)
			self.__msg(text)
			raise PhyError(text)
