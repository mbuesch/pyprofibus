# -*- coding: utf-8 -*-
#
# Driver for FPGA based PROFIBUS PHY.
#
# Copyright (c) 2019 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus.compat import *

import time

from pyprofibus.phy_fpga_driver.exceptions import *
from pyprofibus.phy_fpga_driver.messages import *
from pyprofibus.phy_fpga_driver.io import *
from pyprofibus.util import monotonic_time, FaultDebouncer


__all__ = [
	"FpgaPhyDriver",
]


class FpgaPhyDriver(object):
	"""Driver for FPGA based PROFIBUS PHY.
	"""

	FPGA_CLK_HZ		= 24 * 1e6
	PING_INTERVAL		= 0.1
	DEB_INTERVAL		= 1.0

	def __init__(self, spiDev=0, spiChipSelect=0, spiSpeedHz=1000000):
		self.__baudrate = 9600
		self.__ioProc = None
		self.__nextPing = monotonic_time()
		self.__receivedPong = False
		self.__spiDev = spiDev
		self.__spiChipSelect = spiChipSelect
		self.__spiSpeedHz = spiSpeedHz

		try:
			self.__startup()
		except FpgaPhyError as e:
			try:
				self.shutdown()
			except FpgaPhyError:
				pass
			raise e

	def __startup(self):
		"""Startup the driver.
		"""
		self.shutdown()

		self.__faultParity = FaultDebouncer()
		self.__faultMagic = FaultDebouncer()
		self.__faultLen = FaultDebouncer()
		self.__faultPBLen = FaultDebouncer()
		self.__nextFaultDebounce = monotonic_time() + self.DEB_INTERVAL

		# Start the communication process.
		self.__ioProc = FpgaPhyProc(self.__spiDev, self.__spiChipSelect, self.__spiSpeedHz)
		if not self.__ioProc.start():
			self.__ioProc = None
			raise FpgaPhyError("Failed to start I/O process.")

		# Reset the FPGA.
		# But first ping the device to make sure SPI communication works.
		self.__ping()
		self.__controlSend(FpgaPhyMsgCtrl(FpgaPhyMsgCtrl.SPICTRL_SOFTRESET))
		time.sleep(0.01)
		self.__ping()

		# Get the FPGA status to clear all errors.
		self.__fetchStatus()

		# Clear all event counters in I/O proc.
		self.__ioProc.getEventStatus()

		self.__nextPing = monotonic_time() + self.PING_INTERVAL
		self.__receivedPong = True

	def __ping(self, tries=3):
		"""Ping the FPGA and check if a pong can be received.
		Raises a FpgaPhyError on failure.
		"""
		for i in range(tries - 1, -1, -1):
			try:
				pingMsg = FpgaPhyMsgCtrl(FpgaPhyMsgCtrl.SPICTRL_PING)
				pongMsg = self.__controlTransferSync(pingMsg,
							FpgaPhyMsgCtrl.SPICTRL_PONG)
				if not pongMsg:
					raise FpgaPhyError("Cannot communicate with "
							    "PHY. Timeout.")
				break
			except FpgaPhyError as e:
				if i <= 0:
					raise e

	def __fetchStatus(self):
		"""Fetch the FPGA status.
		"""
		txMsg = FpgaPhyMsgCtrl(FpgaPhyMsgCtrl.SPICTRL_GETSTATUS)
		rxMsg = self.__controlTransferSync(txMsg, FpgaPhyMsgCtrl.SPICTRL_STATUS)
		if not rxMsg:
			raise FpgaPhyError("Failed to get status.")
		return rxMsg.ctrlData

	def shutdown(self):
		"""Shutdown the driver.
		"""
		if self.__ioProc is not None:
			self.__ioProc.shutdownProc()
			self.__ioProc = None

	def restart(self):
		"""Restart the driver and the FPGA.
		"""
		self.__startup()
		self.setBaudRate(self.__baudrate)

	def setBaudRate(self, baudrate):
		"""Configure the PHY baud rate.
		"""
		if self.__ioProc is None:
			raise FpgaPhyError("Cannot set baud rate. "
					    "Driver not initialized.")
		if baudrate < 9600 or baudrate > 12000000:
			raise FpgaPhyError("Invalid baud rate %d." % baudrate)

		clksPerSym = int(round(self.FPGA_CLK_HZ / baudrate))
		if not (1 <= clksPerSym <= 0xFFFFFF):
			raise FpgaPhyError("Invalid baud rate %d. "
					   "CLK divider out of range." % baudrate)

		realBaudrate = int(round(self.FPGA_CLK_HZ / clksPerSym))
		baudError = abs(baudrate - realBaudrate) / baudrate
		maxError = 0.005
		if baudError > maxError:
			raise FpgaPhyError("Invalid baud rate %d. "
					   "CLK divider maximum error threshold (%.1f%%) exceed "
					   "(actual error = %.1f%%)." % (
					   baudrate,
					   maxError * 100.0,
					   baudError * 100.0))

		txMsg = FpgaPhyMsgCtrl(FpgaPhyMsgCtrl.SPICTRL_BAUD,
					ctrlData=clksPerSym)
		rxMsg = self.__controlTransferSync(txMsg, FpgaPhyMsgCtrl.SPICTRL_BAUD)
		if not rxMsg or rxMsg.ctrlData != txMsg.ctrlData:
			raise FpgaPhyError("Failed to set baud rate.")
		self.__baudrate = baudrate

	def __controlTransferSync(self, ctrlMsg, rxCtrlMsgId):
		"""Transfer a control message and wait for a reply.
		"""
		self.__controlSend(ctrlMsg)
		for j in range(50):
			for rxMsg in self.__controlReceive():
				if rxMsg.ctrl == rxCtrlMsgId:
					return rxMsg
			time.sleep(0.01)
		return None

	def __controlSend(self, ctrlMsg):
		"""Send a FpgaPhyMsgCtrl() control message.
		"""
		self.__ioProc.controlSend(ctrlMsg)

	def __controlReceive(self):
		"""Get a list of received control messages.
		Returns a list of FpgaPhyMsgCtrl().
		The returned list might be empty.
		"""
		return self.__ioProc.controlReceive()

	def __handleControl(self):
		"""Receive and handle pending control messages.
		"""
		rxMsgs = self.__controlReceive()
		for rxMsg in rxMsgs:
			ctrl = rxMsg.ctrl
			if ctrl == FpgaPhyMsgCtrl.SPICTRL_NOP:
				pass # Nothing to do.
			elif ctrl == FpgaPhyMsgCtrl.SPICTRL_PONG:
				self.__receivedPong = True
			else:
				raise FpgaPhyError("Received unexpected "
						   "control message: %s" % str(rxMsg))

	def __handleEvents(self, events):
		if events & (1 << FpgaPhyProc.EVENT_RESET):
			statusBits = self.__fetchStatus()
			info = []
			if statusBits & (1 << FpgaPhyMsgCtrl.SPISTAT_PONRESET):
				info.append("power-on-reset")
			if statusBits & (1 << FpgaPhyMsgCtrl.SPISTAT_HARDRESET):
				info.append("hard-reset")
			if statusBits & (1 << FpgaPhyMsgCtrl.SPISTAT_SOFTRESET):
				info.append("soft-reset")
			info.append("0x%02X" % statusBits)
			raise FpgaPhyError("Reset detected (%s)." % (
					   " / ".join(info)))

		if events & (1 << FpgaPhyProc.EVENT_NEWSTAT):
			statusBits = self.__fetchStatus()
			if statusBits & (1 << FpgaPhyMsgCtrl.SPISTAT_TXOVR):
				raise FpgaPhyError("FPGA TX buffer overflow.")
			if statusBits & (1 << FpgaPhyMsgCtrl.SPISTAT_RXOVR):
				raise FpgaPhyError("FPGA RX buffer overflow.")
			if statusBits & (1 << FpgaPhyMsgCtrl.SPISTAT_CTRLCRCERR):
				raise FpgaPhyError("FPGA control message CRC error.")

		if events & (1 << FpgaPhyProc.EVENT_PARERR):
			self.__faultParity.fault()
		else:
			self.__faultParity.ok()

		if events & (1 << FpgaPhyProc.EVENT_NOMAGIC):
			self.__faultMagic.fault()
		else:
			self.__faultMagic.ok()

		if events & (1 << FpgaPhyProc.EVENT_INVALLEN):
			self.__faultLen.fault()
		else:
			self.__faultLen.ok()

		if events & (1 << FpgaPhyProc.EVENT_PBLENERR):
			self.__faultPBLen.fault()
		else:
			self.__faultPBLen.ok()

		if self.__faultParity.get() >= 3:
			raise FpgaPhyError("Detected FPGA message parity errors.")
		if self.__faultMagic.get() >= 3:
			raise FpgaPhyError("Detected FPGA message MAGC-field errors.")
		if self.__faultLen.get() >= 3:
			raise FpgaPhyError("Detected FPGA message LEN-field errors.")
		if self.__faultPBLen.get() >= 5:
			raise FpgaPhyError("Detected Profibus telegram LEN-field errors.")

	def telegramSend(self, txTelegramData):
		"""Send a PROFIBUS telegram.
		"""
		ioProc = self.__ioProc
		if ioProc is None:
			raise FpgaPhyError("telegramSend: No I/O process")

		now = monotonic_time()

		# Handle keep-alive-ping.
		if now >= self.__nextPing:
			if not self.__receivedPong:
				# We did not receive the PONG to the previous PING.
				raise FpgaPhyError("PING to FPGA failed.")
			self.__nextPing = now + self.PING_INTERVAL
			self.__receivedPong = False
			# Send a PING to the FPGA to check if it is still alive.
			pingMsg = FpgaPhyMsgCtrl(FpgaPhyMsgCtrl.SPICTRL_PING)
			self.__controlSend(pingMsg)

		# Send the telegram data.
		ioProc.dataSend(txTelegramData)

	def telegramReceive(self):
		"""Get a list of received PROFIBUS telegrams.
		Returns a list of bytes.
		The returned list might be empty.
		"""
		ioProc = self.__ioProc
		if ioProc is None:
			raise FpgaPhyError("telegramReceive: No I/O process")

		rxTelegrams = []
		now = monotonic_time()

		# Handle I/O process events.
		events = ioProc.getEventStatus()
		if events:
			self.__nextFaultDebounce = now + self.DEB_INTERVAL
			self.__handleEvents(events)
		elif now >= self.__nextFaultDebounce:
			self.__nextFaultDebounce = now + self.DEB_INTERVAL
			self.__handleEvents(0) # No events

		# Handle received control data.
		if ioProc.controlAvailable():
			self.__nextPing = now + self.PING_INTERVAL
			self.__handleControl()

		# Handle received telegram data.
		if ioProc.dataAvailable():
			self.__nextPing = now + self.PING_INTERVAL
			rxTelegrams = ioProc.dataReceive()

		return rxTelegrams
