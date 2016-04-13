#
# PROFIBUS DP - Communication Processor PHY access library
#
# Copyright (c) 2016 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from pyprofibus.phy import *

import serial


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
			self.__serial.close()
			self.__serial = None
		super(CpPhySerial, self).close()

	# Poll for received packet.
	# timeout => In seconds. 0 = none, Negative = unlimited.
	def poll(self, timeout = 0):
		pass#TODO

	def setConfig(self, baudrate = CpPhy.BAUD_19200):
		self.close()
		try:
			self.__serial = serial.Serial(
				port = self.__port,
				baudrate = baudrate,
				bytesize = 8,
				parity = serial.PARITY_EVEN,
				stopbits = serial.STOPBITS_ONE,
				timeout = 1.0,
				xonxoff = False,
				rtscts = False,
				dsrdtr = False)
		except serial.SerialException as e:
			raise PhyError("Failed to set CP-PHY "
				"configuration:\n" + str(e))

	def profibusSend_SDN(self, telegramData):
		self.__serial.write(bytearray(telegramData))

	def profibusSend_SRD(self, telegramData):
		self.profibusSend_SDN(telegramData)
