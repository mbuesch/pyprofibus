#
# PROFIBUS DP - Communication Processor PHY access library
#
# Copyright (c) 2016 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from pyprofibus.phy import *
from pyprofibus.fdl import FdlTelegram

import sys
import time
import binascii

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


class CpPhySerial(CpPhy):
	"""pyserial based PROFIBUS CP PHYsical layer
	"""

	def __init__(self, port, debug = False):
		super(CpPhySerial, self).__init__(debug = debug)
		self.__port = port
		self.__serial = None
		self.setConfig()

	def close(self):
		if self.__serial:
			try:
				self.__serial.close()
			except serial.SerialException as e:
				pass
			self.__serial = None
			self.__rxBuf = bytearray()
		super(CpPhySerial, self).close()

	def __discard(self):
		if self.__serial:
			self.__serial.flushInput()
			self.__serial.flushOutput()

	# Poll for received packet.
	# timeout => In seconds. 0 = none, Negative = unlimited.
	def poll(self, timeout = 0):
		ret, rxBuf, s, size = None, self.__rxBuf, self.__serial, -1
		getSize = FdlTelegram.getSizeFromRaw
		timeoutStamp = time.clock() + timeout
		try:
			while True:
				if len(rxBuf) < 1:
					rxBuf += s.read(1)
				elif len(rxBuf) < 3:
					try:
						size = getSize(rxBuf)
						readLen = size
					except ProfibusError:
						readLen = 3
					rxBuf += s.read(readLen - len(rxBuf))
				elif len(rxBuf) >= 3:
					try:
						size = getSize(rxBuf)
					except ProfibusError:
						rxBuf = bytearray()
						self.__discard()
						raise PhyError("PHY-serial: "
							"Failed to get received "
							"telegram size:\n"
							"Invalid telegram format.")
					if len(rxBuf) < size:
						rxBuf += s.read(size - len(rxBuf))

				if len(rxBuf) == size:
					ret, rxBuf = rxBuf, bytearray()
					break

				if timeout >= 0 and\
				   time.clock() >= timeoutStamp:
					break
		except serial.SerialException as e:
			rxBuf = bytearray()
			self.__discard()
			raise PhyError("PHY-serial: Failed to receive "
				"telegram:\n" + str(e))
		finally:
			self.__rxBuf = rxBuf
		if self.debug and ret:
			print("PHY-serial: RX %s" %\
			      binascii.b2a_hex(ret).decode())
		return ret

	def setConfig(self, baudrate = CpPhy.BAUD_19200):
		self.close()
		try:
			self.__serial = serial.Serial(
				port = self.__port,
				baudrate = baudrate,
				bytesize = 8,
				parity = serial.PARITY_EVEN,
				stopbits = serial.STOPBITS_ONE,
				timeout = 0,
				xonxoff = False,
				rtscts = False,
				dsrdtr = False)
			self.__rxBuf = bytearray()
		except serial.SerialException as e:
			raise PhyError("Failed to set CP-PHY "
				"configuration:\n" + str(e))
		self.__setConfigPiLC(baudrate)

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

	def profibusSend_SDN(self, telegramData):
		try:
			telegramData = bytearray(telegramData)
			if self.debug:
				print("PHY-serial: TX %s" %\
				      binascii.b2a_hex(telegramData).decode())
			self.__serial.write(telegramData)
		except serial.SerialException as e:
			raise PhyError("PHY-serial: Failed to transmit "
				"telegram:\n" + str(e))

	profibusSend_SRD = profibusSend_SDN
