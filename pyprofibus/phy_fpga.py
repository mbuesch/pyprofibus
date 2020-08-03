# -*- coding: utf-8 -*-
#
# PROFIBUS DP - Communication Processor PHY access library
#
# Copyright (c) 2019 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus.compat import *

from pyprofibus.phy import *
from pyprofibus.fdl import *
from pyprofibus.dp import *
from pyprofibus.phy_fpga_driver import *

from collections import deque


__all__ = [
	"CpPhyFPGA",
]


class CpPhyFPGA(CpPhy):
	"""FPGA based PROFIBUS CP PHYsical layer
	"""

	PFX = "PHY-fpga: "

	def __init__(self, spiBus, spiCS, spiSpeedHz, *args, **kwargs):
		super(CpPhyFPGA, self).__init__(*args, **kwargs)
		self.__rxDeque = deque()
		self.__driver = None
		self.__spiBus = spiBus
		self.__spiCS = spiCS
		self.__spiSpeedHz = spiSpeedHz

	def close(self):
		"""Close the PHY device.
		"""
		if self.__driver is not None:
			try:
				self.__driver.shutdown()
			except FpgaPhyError as e:
				pass
			self.__rxDeque.clear()
			self.__driver = None
		super(CpPhyFPGA, self).close()

	def __tryRestartDriver(self, exception):
		try:
			self._debugMsg("Driver exception: %s" % str(exception))
			if self.__driver is not None:
				self.__driver.restart()
		except FpgaPhyError as e:
			self._debugMsg("Error recovery restart failed: %s" % (
				str(e)))

	def sendData(self, telegramData, srd):
		"""Send data to the physical line.
		"""
		if self.__driver is None:
			return

		if self.debug:
			self._debugMsg("TX   %s" % bytesToHex(telegramData))

		try:
			self.__driver.telegramSend(telegramData)
		except FpgaPhyError as e:
			self.__tryRestartDriver(e)

	def pollData(self, timeout=0.0):
		"""Poll received data from the physical line.
		timeout => timeout in seconds.
			   0 = no timeout, return immediately.
			   negative = unlimited.
		"""
		if self.__driver is None:
			return None

		telegramData = None
		try:
			if self.__rxDeque:
				telegramData = self.__rxDeque.popleft()
			else:
				timeoutStamp = monotonic_time() + timeout#TODO
				telegramDataList = self.__driver.telegramReceive()
				count = len(telegramDataList)
				if count >= 1:
					telegramData = telegramDataList[0]
					if count >= 2:
						self.__rxDeque.extend(telegramDataList[1:])
		except FpgaPhyError as e:
			self.__tryRestartDriver(e)
			telegramData = None

		if self.debug and telegramData:
			self._debugMsg("RX   %s" % bytesToHex(telegramData))
		return telegramData

	def setConfig(self, baudrate=CpPhy.BAUD_9600, *args, **kwargs):
		super(CpPhyFPGA, self).setConfig(baudrate=baudrate, *args, **kwargs)
		self.close()
		try:
			self.__driver = FpgaPhyDriver(spiDev=self.__spiBus,
						      spiChipSelect=self.__spiCS,
						      spiSpeedHz=self.__spiSpeedHz)
			self.__driver.setBaudRate(baudrate)
		except FpgaPhyError as e:
			raise PhyError(self.PFX + ("Failed to setup driver:\n%s" % str(e)))
