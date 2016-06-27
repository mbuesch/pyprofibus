# -*- coding: utf-8 -*-
#
# PROFIBUS DP - Communication Processor PHY access library
#
# Copyright (c) 2016 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus.compat import *

from pyprofibus.phy import *
from pyprofibus.fdl import *
from pyprofibus.dp import *


class CpPhyDummySlave(CpPhy):
	"""Dummy slave PROFIBUS CP PHYsical layer
	"""

	def __init__(self, debug = False):
		super(CpPhyDummySlave, self).__init__(debug = debug)
		self.__pollQueue = []

	def __msg(self, message):
		if self.debug:
			print("CpPhyDummySlave: %s" % message)

	def close(self):
		self.__pollQueue = []
		super(CpPhyDummySlave, self).close()

	# Poll for received packet.
	# timeout => In seconds. 0 = none, Negative = unlimited.
	def poll(self, timeout = 0):
		try:
			telegramData = self.__pollQueue.pop(0)
		except IndexError as e:
			return None
		self.__msg("Receiving    %s" % bytesToHex(telegramData))
		return telegramData

	def setConfig(self, baudrate = CpPhy.BAUD_9600):
		self.__msg("Baudrate = %d" % baudrate)
		self.__pollQueue = []

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
				du = bytearray([ d ^ 0xFF for d in dp.du ])
				telegram = DpTelegram_DataExchange_Con(da = fdl.sa,
								       sa = fdl.da,
								       du = du)
				self.__pollQueue.append(telegram.toFdlTelegram().getRawData())
				return

			self.__msg("Dropping SRD telegram: %s" % str(fdl))
		except ProfibusError as e:
			text = "SRD mock-send error: %s" % str(e)
			self.__msg(text)
			raise PhyError(text)

	def profibusSend_SDN(self, telegramData):
		telegramData = bytearray(telegramData)
		self.__msg("Sending SDN  %s" % bytesToHex(telegramData))
		self.__mockSend(telegramData, srd = False)

	def profibusSend_SRD(self, telegramData):
		telegramData = bytearray(telegramData)
		self.__msg("Sending SRD  %s" % bytesToHex(telegramData))
		self.__mockSend(telegramData, srd = True)
