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

from pyprofibus.phy_fpga_driver.exceptions import *


__all__ = [
	"FpgaPhyMsg",
	"FpgaPhyMsgCtrl",
]


class FpgaPhyMsg(object):
	SPI_MS_MAGIC	= 0xAA
	SPI_SM_MAGIC	= 0x55

	PADDING		= 0x00
	PADDING_BYTE	= bytes([PADDING])

	SPI_FLG_START	= 0
	SPI_FLG_CTRL	= 1
	SPI_FLG_NEWSTAT	= 2
	SPI_FLG_RESET	= 3
	SPI_FLG_UNUSED4	= 4
	SPI_FLG_UNUSED5	= 5
	SPI_FLG_UNUSED7	= 6
	SPI_FLG_PARITY	= 7

	LEN_UNKNOWN	= -1
	LEN_NEEDMORE	= -2
	LEN_ERROR	= -3

	CRC_POLYNOMIAL	= 0x07

	SD1		= 0x10
	SD2		= 0x68
	SD3		= 0xA2
	SD4		= 0xDC
	SC		= 0xE5

	@staticmethod
	def crc8(dataBytes, crc=0xFF, P=CRC_POLYNOMIAL):
		for data in dataBytes:
			data ^= crc
			for i in range(8):
				data = ((data << 1) ^ (P if (data & 0x80) else 0)) & 0xFF
			crc = data
		return crc

	@classmethod
	def parity(cls, value):
		"""Calculate odd parity on 8 bits.
		"""
		return ((value & 1) ^
			((value >> 1) & 1) ^
			((value >> 2) & 1) ^
			((value >> 3) & 1) ^
			((value >> 4) & 1) ^
			((value >> 5) & 1) ^
			((value >> 6) & 1) ^
			((value >> 7) & 1) ^ 1)

	@classmethod
	def calcLen(cls, dataBytes):
		dataBytesLen = len(dataBytes)
		if dataBytesLen > 0:
			firstByte = dataBytes[0]
			if firstByte == cls.SC:
				return 1
			elif firstByte == cls.SD1:
				return 6
			elif firstByte == cls.SD2:
				if dataBytesLen >= 4:
					lenField = dataBytes[1]
					if (lenField == dataBytes[2] and
					    lenField >= 4 and
					    lenField <= 249 and
					    dataBytes[3] == cls.SD2):
						return lenField + 6
					else:
						return cls.LEN_ERROR
				return cls.LEN_NEEDMORE
			elif firstByte == cls.SD3:
				return 14
			elif firstByte == cls.SD4:
				return 3
		return cls.LEN_UNKNOWN

class FpgaPhyMsgCtrl(FpgaPhyMsg):
	# SPI control message IDs.
	SPICTRL_NOP		= 0
	SPICTRL_PING		= 1
	SPICTRL_PONG		= 2
	SPICTRL_SOFTRESET	= 3
	SPICTRL_GETSTATUS	= 4
	SPICTRL_STATUS		= 5
	SPICTRL_GETBAUD		= 6
	SPICTRL_BAUD		= 7

	# Status message data bits.
	SPISTAT_PONRESET	= 0
	SPISTAT_HARDRESET	= 1
	SPISTAT_SOFTRESET	= 2
	SPISTAT_TXOVR		= 3
	SPISTAT_RXOVR		= 4
	SPISTAT_CTRLCRCERR	= 5

	CTRL_LEN = 8

	def __init__(self, ctrl, ctrlData=0, flg=0):
		self.flg = flg | (1 << self.SPI_FLG_CTRL)
		self.ctrl = ctrl
		self.ctrlData = ctrlData

	def toBytes(self):
		data = bytearray(8)
		data[0] = self.SPI_MS_MAGIC
		data[1] = 1 << self.SPI_FLG_CTRL
		data[1] |= self.parity(data[1]) << self.SPI_FLG_PARITY
		data[2] = self.ctrl & 0xFF
		data[3] = (self.ctrlData >> 24) & 0xFF
		data[4] = (self.ctrlData >> 16) & 0xFF
		data[5] = (self.ctrlData >> 8) & 0xFF
		data[6] = self.ctrlData & 0xFF
		data[7] = self.crc8(data[2:7])
		return data

	@classmethod
	def fromBytes(cls, data):
		if data[0] != cls.SPI_SM_MAGIC:
			raise FpgaPhyError("FPGA control message: "
					   "Invalid MAGC field.")
		flg = data[1]
		if cls.parity(flg):
			raise FpgaPhyError("FPGA control message: "
					   "Invalid parity bit.")
		if not (flg & (1 << cls.SPI_FLG_CTRL)):
			raise FpgaPhyError("FPGA control message: "
					   "CTRL bit is not set.")
		ctrl = data[2]
		ctrlData = data[3] << 24
		ctrlData |= data[4] << 16
		ctrlData |= data[5] << 8
		ctrlData |= data[6]
		crc = data[7]
		crcExpected = cls.crc8(data[2:7])
		if crc != crcExpected:
			raise FpgaPhyError("FPGA control message: "
					   "CRC error.")
		return cls(ctrl, ctrlData, flg)

	def __str__(self):
		try:
			name = {
				self.SPICTRL_NOP	: "NOP",
				self.SPICTRL_PING	: "PING",
				self.SPICTRL_PONG	: "PONG",
				self.SPICTRL_SOFTRESET	: "SOFTRESET",
				self.SPICTRL_GETSTATUS	: "GETSTATUS",
				self.SPICTRL_STATUS	: "STATUS",
				self.SPICTRL_GETBAUD	: "GETBAUD",
				self.SPICTRL_BAUD	: "BAUD",
			}[self.ctrl]
		except KeyError as e:
			name = "%02X" % self.ctrl
		return "PHYControl(%s, 0x%08X)" % (name, self.ctrlData)
