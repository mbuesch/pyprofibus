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
from pyprofibus.fdl import FdlTelegram
from pyprofibus.util import *

import sys

try:
	import serial
except ImportError as e:
	if "PyPy" in sys.version and\
	   sys.version_info[0] == 2:
		# We are on PyPy2.
		# Try to import CPython2's serial.
		import glob
		sys.path.extend(glob.glob("/usr/lib/python2*/*-packages/"))
		import serial
	else:
		raise e
try:
	import serial.rs485
except ImportError:
	pass

__all__ = [
	"CpPhySerial",
]

class CpPhySerial(CpPhy):
	"""pyserial based PROFIBUS CP PHYsical layer
	"""

	__slots__ = (
		"__discardTimeout",
		"__rxBuf",
		"__serial",
	)

	PFX = "PHY-serial: "

	def __init__(self, port, useRS485Class=False, *args, **kwargs):
		"""port => "/dev/ttySx"
		debug => enable/disable debugging.
		useRS485Class => Use serial.rs485.RS485, if True. (might be slower).
		"""
		super(CpPhySerial, self).__init__(*args, **kwargs)
		self.__discardTimeout = None
		self.__rxBuf = bytearray()
		try:
			if useRS485Class:
				if not hasattr(serial, "rs485"):
					raise PhyError("Module serial.rs485 "
						"is not available. "
						"Please use useRS485Class=False.")
				self.__serial = serial.rs485.RS485()
			else:
				self.__serial = serial.Serial()
			self.__serial.port = port
			self.__serial.baudrate = CpPhy.BAUD_9600
			self.__serial.bytesize = 8
			self.__serial.parity = serial.PARITY_EVEN
			self.__serial.stopbits = serial.STOPBITS_ONE
			self.__serial.timeout = 0
			self.__serial.xonxoff = False
			self.__serial.rtscts = False
			self.__serial.dsrdtr = False
			if useRS485Class:
				self.__serial.rs485_mode = serial.rs485.RS485Settings(
					rts_level_for_tx = True,
					rts_level_for_rx = False,
					loopback = False,
					delay_before_tx = 0.0,
					delay_before_rx = 0.0
				)
			self.__serial.open()
		except (serial.SerialException, ValueError) as e:
			raise PhyError("Failed to open "
				"serial port:\n" + str(e))

	def close(self):
		try:
			self.__serial.close()
		except serial.SerialException as e:
			pass
		self.__rxBuf = bytearray()
		super(CpPhySerial, self).close()

	def __discard(self):
		s = self.__serial
		if s:
			s.flushInput()
			s.flushOutput()
		if monotonic_time() >= self.__discardTimeout:
			self.__discardTimeout = None

	def __startDiscard(self):
		self.__discardTimeout = monotonic_time() + 0.01

	# Poll for received packet.
	# timeout => In seconds. 0.0 = none, Negative = unlimited.
	def pollData(self, timeout=0.0):
		if timeout > 0.0:
			timeoutStamp = monotonic_time() + timeout
		ret = None
		rxBuf = self.__rxBuf
		ser = self.__serial
		size = -1
		getSize = FdlTelegram.getSizeFromRaw

		while self.__discardTimeout is not None:
			self.__discard()
			if timeout > 0.0 and monotonic_time() >= timeoutStamp:
				return None

		try:
			rxBufLen = len(rxBuf)
			while True:
				if rxBufLen < 1:
					rxBuf.extend(ser.read(1))
				elif rxBufLen < 3:
					if size < 0:
						size = getSize(rxBuf)
					readLen = (size if size > 0 else 3) - rxBufLen
					if readLen > 0:
						rxBuf.extend(ser.read(readLen))
				elif rxBufLen >= 3:
					if size < 0:
						size = getSize(rxBuf)
						if size < 0:
							if self.debug and rxBuf:
								self._debugMsg("RX (fragment)   %s" % bytesToHex(rxBuf))
							rxBuf = bytearray()
							self.__startDiscard()
							raise PhyError("PHY-serial: "
								"Failed to get received telegram size: "
								"Invalid telegram format.")
					if rxBufLen < size:
						rxBuf.extend(ser.read(size - rxBufLen))

				rxBufLen = len(rxBuf)
				if rxBufLen == size:
					ret = rxBuf
					rxBuf = bytearray()
					rxBufLen = 0
					break

				if (timeout == 0.0 or
				    (timeout > 0.0 and monotonic_time() >= timeoutStamp)):
					break
		except serial.SerialException as e:
			if self.debug and rxBuf:
				self._debugMsg("RX (fragment)   %s" % bytesToHex(rxBuf))
			rxBuf = bytearray()
			self.__startDiscard()
			raise PhyError("PHY-serial: Failed to receive "
				"telegram:\n" + str(e))
		finally:
			self.__rxBuf = rxBuf
		if self.debug and ret:
			self._debugMsg("RX   %s" % bytesToHex(ret))
		return ret

	def sendData(self, telegramData, srd):
		if self.__discardTimeout is not None:
			return
		try:
			if self.debug:
				self._debugMsg("TX   %s" % bytesToHex(telegramData))
			self.__serial.write(telegramData)
		except serial.SerialException as e:
			raise PhyError("PHY-serial: Failed to transmit "
				"telegram:\n" + str(e))

	def setConfig(self, baudrate=CpPhy.BAUD_9600, rtscts=False, dsrdtr=False, *args, **kwargs):
		wellSuppBaud = (9600, 19200)
		if baudrate not in wellSuppBaud and not isMicropython:
			# The hw/driver might silently ignore the baudrate
			# and use the already set value from __init__().
			self._warningMsg("The configured baud rate %d baud "
					 "might not be supported by the hardware. "
					 "Note that some hardware silently falls back "
					 "to 9600 baud for unsupported rates. "
					 "Commonly well supported baud rates by serial "
					 "hardware are: %s." % (
					 baudrate,
					 ", ".join(str(b) for b in wellSuppBaud)))
		try:
			if baudrate != self.__serial.baudrate or rtscts != self.__serial.rtscts or dsrdtr != self.__serial.dsrdtr:
				self.__serial.close()
				self.__serial.baudrate = baudrate
				self.__serial.rtscts = rtscts
				self.__serial.dsrdtr = dsrdtr
				self.__serial.open()
				self.__rxBuf = bytearray()
		except (serial.SerialException, ValueError) as e:
			raise PhyError("Failed to set CP-PHY "
				"configuration:\n" + str(e))
		self.__setConfigPiLC(baudrate)
		super(CpPhySerial, self).setConfig(baudrate=baudrate,
						   rtscts=rtscts,
						   dsrdtr=dsrdtr,
						   *args, **kwargs)

	def __setConfigPiLC(self, baudrate):
		"""Reconfigure the PiLC HAT, if available.
		"""
		try:
			import libpilc.raspi_hat_conf as raspi_hat_conf
		except ImportError as e:
			return
		if not raspi_hat_conf.PilcConf.havePilcHat():
			return
		try:
			conf = raspi_hat_conf.PilcConf()
			conf.setBaudrate(baudrate / 1000.0)
		except raspi_hat_conf.PilcConf.Error as e:
			raise PhyError("Failed to configure PiLC HAT:\n%s" %\
				str(e))
