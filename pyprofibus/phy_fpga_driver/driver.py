# -*- coding: utf-8 -*-
#
# Driver for FPGA based PROFIBUS PHY.
#
# Copyright (c) 2019 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

import multiprocessing
import mmap
import spidev
import time
import sys

from pyprofibus.util import monotonic_time
from pyprofibus.phy import PhyError


__all__ = [
	"FpgaPhyDriver",
	"FpgaPhyError",
]


class FpgaPhyError(PhyError):
	def __init__(self, msg, *args, **kwargs):
		msg = "PHY-FPGA: " + str(msg)
		super(FpgaPhyError, self).__init__(msg, *args, **kwargs)

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
	SPICTRL_NOP		= 0
	SPICTRL_PING		= 1
	SPICTRL_PONG		= 2
	SPICTRL_SOFTRESET	= 3
	SPICTRL_GETSTATUS	= 4
	SPICTRL_STATUS		= 5
	SPICTRL_GETBAUD		= 6
	SPICTRL_BAUD		= 7

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
			return None
		flg = data[1]
		if cls.parity(flg):
			return None
		if not (flg & (1 << cls.SPI_FLG_CTRL)):
			return None
		ctrl = data[2]
		ctrlData = data[3] << 24
		ctrlData |= data[4] << 16
		ctrlData |= data[5] << 8
		ctrlData |= data[6]
		crc = data[7]
		crcExpected = cls.crc8(data[2:7])
		if crc != crcExpected:
			return None
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

class FpgaPhyProc(multiprocessing.Process):
	"""I/O process.
	"""

	# Event IDs
	EVENT_NEWSTAT			= 0
	EVENT_RESET			= 1
	EVENT_PARERR			= 2
	EVENT_NOMAGIC			= 3
	EVENT_INVALLEN			= 4
	EVENT_PBLENERR			= 5

	# Offsets into __shmStatus
	STATUS_RUNNING			= 0x0
	STATUS_STOP			= 0x40
	STATUS_ERROR			= 0x80
	STATUS_CTRL_TXCOUNT		= 0xC0
	STATUS_CTRL_RXCOUNT		= 0x100
	STATUS_DATA_TXCOUNT		= 0x140
	STATUS_DATA_RXCOUNT		= 0x180
	STATUS_EVENTCOUNT_BASE		= 0x1C0
	STATUS_EVENTCOUNT_NEWSTAT	= STATUS_EVENTCOUNT_BASE + EVENT_NEWSTAT
	STATUS_EVENTCOUNT_RESET		= STATUS_EVENTCOUNT_BASE + EVENT_RESET
	STATUS_EVENTCOUNT_PARERR	= STATUS_EVENTCOUNT_BASE + EVENT_PARERR
	STATUS_EVENTCOUNT_NOMAGIC	= STATUS_EVENTCOUNT_BASE + EVENT_NOMAGIC
	STATUS_EVENTCOUNT_INVALLEN	= STATUS_EVENTCOUNT_BASE + EVENT_INVALLEN
	STATUS_EVENTCOUNT_PBLENERR	= STATUS_EVENTCOUNT_BASE + EVENT_PBLENERR

	# I/O process return codes.
	ERROR_NONE			= 0
	ERROR_OSERROR			= 1
	ERROR_PERMISSION		= 2

	# Meta data offsets.
	META_OFFS_LO			= 0
	META_OFFS_HI			= 1
	META_LEN			= 2
	METASTRUCT_SIZE			= 3

	def __init__(self, spiDev, spiChipSelect, spiSpeedHz):
		super(FpgaPhyProc, self).__init__()

		self.__rxDataCount = 0
		self.__rxCtrlCount = 0
		self.__rxCtrlRdOffs = 0
		self.__txCtrlWrOffs = 0
		self.__txDataWrOffs = 0
		self.__eventCountNewStat = 0
		self.__eventCountReset = 0
		self.__eventCountParErr = 0
		self.__eventCountNoMagic = 0
		self.__eventCountInvalLen = 0
		self.__eventCountPBLenErr = 0

		self.__spiDev = spiDev
		self.__spiChipSelect = spiChipSelect
		self.__spiSpeedHz = spiSpeedHz

		def makeSHM(length):
			shm = mmap.mmap(-1, length)
			shm[0:length] = b"\x00" * length
			return shm

		self.__shmLengths = 4096
		self.__shmMask = self.__shmLengths - 1
		self.__shmTxData = makeSHM(self.__shmLengths)
		self.__shmTxDataMeta = makeSHM(self.__shmLengths)
		self.__shmRxData = makeSHM(self.__shmLengths)
		self.__shmRxDataMeta = makeSHM(self.__shmLengths)
		self.__shmTxCtrl = makeSHM(self.__shmLengths)
		self.__shmRxCtrl = makeSHM(self.__shmLengths)
		self.__shmStatus = makeSHM(self.__shmLengths)

	def start(self):
		super(FpgaPhyProc, self).start()
		success = False
		for i in range(500):
			if self.__shmStatus[self.STATUS_RUNNING]:
				success = True
				break
			if self.__shmStatus[self.STATUS_ERROR] != self.ERROR_NONE:
				break
			if not self.is_alive():
				break
			time.sleep(0.01)
		if not success:
			self.shutdownProc()
		return success

	def __incShmStatus(self, index):
		self.__shmStatus[index] = (self.__shmStatus[index] + 1) & 0xFF

	def __ioProcMainLoop(self, spi):
		ctrlWrOffs = 0
		ctrlRdOffs = 0
		dataWrOffs = 0

		txDataCount = 0
		txCtrlCount = 0

		expectedRxLength = 0
		collectedRxLength = 0
		rxDataBuf = bytearray()

		shmMask = self.__shmMask

		CTRL_LEN = FpgaPhyMsgCtrl.CTRL_LEN
		RX_DATA_LEN = 11

		MIN_XFER_LEN = RX_DATA_LEN

		tailData = b""
		while not self.__shmStatus[self.STATUS_STOP]:
			txData = b""

			# Get the TX control data, if any.
			if txCtrlCount != self.__shmStatus[self.STATUS_CTRL_TXCOUNT]:
				# Get the TX control message.
				txData = bytearray(CTRL_LEN)
				for i in range(CTRL_LEN):
					txData[i] = self.__shmTxCtrl[(ctrlRdOffs + i) & shmMask]

				ctrlRdOffs = (ctrlRdOffs + CTRL_LEN) & shmMask
				txCtrlCount = (txCtrlCount + 1) & 0xFF
			# Get the PB TX data, if any.
			elif txDataCount != self.__shmStatus[self.STATUS_DATA_TXCOUNT]:
				metaBegin = txDataCount * self.METASTRUCT_SIZE
				dataRdOffs = self.__shmTxDataMeta[(metaBegin + self.META_OFFS_LO) & shmMask]
				dataRdOffs |= self.__shmTxDataMeta[(metaBegin + self.META_OFFS_HI) & shmMask] << 8
				dataRdLen = self.__shmTxDataMeta[(metaBegin + self.META_LEN) & shmMask]

				# Construct the TX data message.
				txData = bytearray(dataRdLen + 2)
				txData[0] = FpgaPhyMsg.SPI_MS_MAGIC
				txData[1] = 1 << FpgaPhyMsg.SPI_FLG_START
				txData[1] |= FpgaPhyMsg.parity(txData[1]) << FpgaPhyMsg.SPI_FLG_PARITY
				for i in range(dataRdLen):
					txData[i + 2] = self.__shmTxData[(dataRdOffs + i) & shmMask]

				txDataCount = (txDataCount + 1) & 0xFF

			# Pad the TX data, if required.
			if len(txData) < MIN_XFER_LEN:
				txData += FpgaPhyMsg.PADDING_BYTE * (MIN_XFER_LEN - len(txData))

			# Run the SPI transfer (transmit and receive).
			rxData = bytes(spi.xfer2(txData))
			# If we have tail data, prepend it to the received data.
			if tailData:
				rxData = tailData + rxData
				tailData = b""

			# Strip all leading padding bytes.
			rxData = rxData.lstrip(FpgaPhyMsg.PADDING_BYTE)
			if not rxData:
				continue

			# The first byte must be the magic byte.
			if rxData[0] != FpgaPhyMsg.SPI_SM_MAGIC:
				# Magic mismatch. Try to find the magic byte.
				self.__incShmStatus(self.STATUS_EVENTCOUNT_NOMAGIC)
				rxData = rxData[1:]
				while rxData and rxData[0] != FpgaPhyMsg.SPI_SM_MAGIC:
					rxData = rxData[1:]
				if not rxData:
					# Magic byte not found.
					continue

			# If the remaining data is not enough, get more bytes.
			if len(rxData) < 3:
				rxData += bytes(spi.xfer2(FpgaPhyMsg.PADDING_BYTE * (3 - len(rxData))))

			# Get and check the received flags field.
			flgField = rxData[1]
			if FpgaPhyMsg.parity(flgField):
				# Parity mismatch.
				self.__incShmStatus(self.STATUS_EVENTCOUNT_PARERR)
				continue
			if flgField & (1 << FpgaPhyMsg.SPI_FLG_RESET):
				# FPGA reset detected.
				self.__incShmStatus(self.STATUS_EVENTCOUNT_RESET)
			if flgField & (1 << FpgaPhyMsg.SPI_FLG_NEWSTAT):
				# New STATUS message available.
				self.__incShmStatus(self.STATUS_EVENTCOUNT_NEWSTAT)

			if flgField & (1 << FpgaPhyMsg.SPI_FLG_CTRL):
				# Received control message
				if len(rxData) < CTRL_LEN:
					rxData += bytes(spi.xfer2(FpgaPhyMsg.PADDING_BYTE * (CTRL_LEN - len(rxData))))

				# Write the control message to SHM.
				for i in range(CTRL_LEN):
					self.__shmRxCtrl[(ctrlWrOffs + i) & shmMask] = rxData[i]
				ctrlWrOffs = (ctrlWrOffs + CTRL_LEN) & shmMask

				# Update the receive count in SHM.
				self.__incShmStatus(self.STATUS_CTRL_RXCOUNT)

				# If there is data left, add it to tail data.
				tailData = rxData[CTRL_LEN : ]
			else:
				# Received data message
				if len(rxData) < RX_DATA_LEN:
					rxData += bytes(spi.xfer2(FpgaPhyMsg.PADDING_BYTE * (RX_DATA_LEN - len(rxData))))

				# If this is a telegram start, clear the temp RX buffers.
				if flgField & (1 << FpgaPhyMsg.SPI_FLG_START):
					expectedRxLength = 0
					collectedRxLength = 0
					rxDataBuf = bytearray()

				# Get the raw PB data.
				rawDataLen = rxData[10]
				if rawDataLen <= 0 or rawDataLen > 8:
					# Invalid length.
					self.__incShmStatus(self.STATUS_EVENTCOUNT_INVALLEN)
					continue
				rawData = rxData[2 : 2 + rawDataLen]
				rxDataBuf += rawData

				# If we don't know the PB telegram length, try to calculate it.
				if expectedRxLength <= 0:
					telegramLen = FpgaPhyMsg.calcLen(rxDataBuf)
					if (telegramLen == FpgaPhyMsg.LEN_ERROR or
					    telegramLen == FpgaPhyMsg.LEN_UNKNOWN):
						# Could not determine telegram length.
						self.__incShmStatus(self.STATUS_EVENTCOUNT_PBLENERR)
						continue
					if telegramLen == FpgaPhyMsg.LEN_NEEDMORE:
						# Need more telegram bytes.
						continue
					expectedRxLength = telegramLen

				# If we know the PB telegram length, check if we have enough data.
				if (expectedRxLength > 0 and
				    len(rxDataBuf) >= expectedRxLength):
					#TODO check if received len is more than expected

					# Write the telegram to SHM.
					for i in range(expectedRxLength):
						self.__shmRxData[(dataWrOffs + i) & shmMask] = rxDataBuf[i]

					# Update receive telegram metadata in SHM.
					count = self.__shmStatus[self.STATUS_DATA_RXCOUNT]
					metaBegin = count * self.METASTRUCT_SIZE
					self.__shmRxDataMeta[(metaBegin + self.META_OFFS_LO) & shmMask] = dataWrOffs & 0xFF
					self.__shmRxDataMeta[(metaBegin + self.META_OFFS_HI) & shmMask] = (dataWrOffs >> 8) & 0xFF
					self.__shmRxDataMeta[(metaBegin + self.META_LEN) & shmMask] = expectedRxLength & 0xFF
					self.__incShmStatus(self.STATUS_DATA_RXCOUNT)

					dataWrOffs = (dataWrOffs + expectedRxLength) & shmMask

					expectedRxLength = 0
					collectedRxLength = 0
					rxDataBuf = bytearray()

				# If there is data left, add it to tail data.
				tailData = rxData[RX_DATA_LEN : ]

	# I/O process
	def run(self):
		self.__shmStatus[self.STATUS_RUNNING] = 0
		errorCode = self.ERROR_NONE
		self.__shmStatus[self.STATUS_ERROR] = errorCode
		spi = None
		try:
			spi = spidev.SpiDev()
			spi.open(self.__spiDev, self.__spiChipSelect)
			spi.max_speed_hz = self.__spiSpeedHz

			self.__shmStatus[self.STATUS_RUNNING] = 1
			self.__ioProcMainLoop(spi)

		except PermissionError as e:
			print("FPGA-PHY error: %s" % str(e), file=sys.stderr)
			errorCode = self.ERROR_PERMISSION
		except OSError as e:
			print("FPGA-PHY error: %s" % str(e), file=sys.stderr)
			errorCode = self.ERROR_OSERROR
		finally:
			self.__shmStatus[self.STATUS_ERROR] = errorCode
			try:
				spi.close()
			except OSError as e:
				pass
			self.__shmStatus[self.STATUS_RUNNING] = 0
		return errorCode

	def shutdownProc(self):
		self.__shmStatus[self.STATUS_STOP] = 1
		if self.is_alive():
			self.join()

	def dataSend(self, txTelegramData):
		shmMask = self.__shmMask
		txLength = len(txTelegramData)
		txCount = self.__shmStatus[self.STATUS_DATA_TXCOUNT]
		metaBegin = txCount * self.METASTRUCT_SIZE

		dataWrOffs = self.__txDataWrOffs
		for i in range(txLength):
			self.__shmTxData[(dataWrOffs + i) & shmMask] = txTelegramData[i]

		self.__shmTxDataMeta[(metaBegin + self.META_OFFS_LO) & shmMask] = dataWrOffs & 0xFF
		self.__shmTxDataMeta[(metaBegin + self.META_OFFS_HI) & shmMask] = (dataWrOffs >> 8) & 0xFF
		self.__shmTxDataMeta[(metaBegin + self.META_LEN) & shmMask] = txLength & 0xFF
		self.__shmStatus[self.STATUS_DATA_TXCOUNT] = (txCount + 1) & 0xFF

		self.__txDataWrOffs = (dataWrOffs + txLength) & shmMask
		return True

	def dataReceive(self):
		rxTelegrams = []
		shmMask = self.__shmMask
		newCount = self.__shmStatus[self.STATUS_DATA_RXCOUNT]
		rxCount = self.__rxDataCount
		while rxCount != newCount:
			metaBegin = rxCount * self.METASTRUCT_SIZE
			dataRdOffs = self.__shmRxDataMeta[(metaBegin + self.META_OFFS_LO) & shmMask]
			dataRdOffs |= self.__shmRxDataMeta[(metaBegin + self.META_OFFS_HI) & shmMask] << 8
			dataRdLen = self.__shmRxDataMeta[(metaBegin + self.META_LEN) & shmMask]

			rxData = bytearray(dataRdLen)
			for i in range(dataRdLen):
				rxData[i] = self.__shmRxData[(dataRdOffs + i) & shmMask]
			rxTelegrams.append(rxData)

			rxCount = (rxCount + 1) & 0xFF
		self.__rxDataCount = rxCount
		return rxTelegrams

	def dataAvailable(self):
		return self.__shmStatus[self.STATUS_DATA_RXCOUNT] != self.__rxDataCount

	def controlSend(self, ctrlMsg):
		CTRL_LEN = ctrlMsg.CTRL_LEN
		shmMask = self.__shmMask
		txCount = self.__shmStatus[self.STATUS_CTRL_TXCOUNT]

		ctrlData = ctrlMsg.toBytes()
		ctrlWrOffs = self.__txCtrlWrOffs
		for i in range(CTRL_LEN):
			self.__shmTxCtrl[(ctrlWrOffs + i) & shmMask] = ctrlData[i]

		self.__shmStatus[self.STATUS_CTRL_TXCOUNT] = (txCount + 1) & 0xFF
		self.__txCtrlWrOffs = (ctrlWrOffs + CTRL_LEN) & shmMask
		return True

	def controlReceive(self):
		rxCtrlMsgs = []
		CTRL_LEN = FpgaPhyMsgCtrl.CTRL_LEN
		shmMask = self.__shmMask
		newCount = self.__shmStatus[self.STATUS_CTRL_RXCOUNT]
		rxCount = self.__rxCtrlCount
		ctrlRdOffs = self.__rxCtrlRdOffs
		while rxCount != newCount:
			rxCtrl = bytearray(CTRL_LEN)
			for i in range(CTRL_LEN):
				rxCtrl[i] = self.__shmRxCtrl[(ctrlRdOffs + i) & shmMask]
			rxCtrlMsgs.append(FpgaPhyMsgCtrl.fromBytes(rxCtrl))

			ctrlRdOffs = (ctrlRdOffs + CTRL_LEN) & shmMask
			rxCount = (rxCount + 1) & 0xFF
		self.__rxCtrlRdOffs = ctrlRdOffs
		self.__rxCtrlCount = rxCount
		return rxCtrlMsgs

	def controlAvailable(self):
		return self.__shmStatus[self.STATUS_CTRL_RXCOUNT] != self.__rxCtrlCount

	def getEventStatus(self):
		events = 0
		if self.__eventCountNewStat != self.__shmStatus[self.STATUS_EVENTCOUNT_NEWSTAT]:
			self.__eventCountNewStat = self.__shmStatus[self.STATUS_EVENTCOUNT_NEWSTAT]
			events |= 1 << self.EVENT_NEWSTAT
		if self.__eventCountReset != self.__shmStatus[self.STATUS_EVENTCOUNT_RESET]:
			self.__eventCountReset = self.__shmStatus[self.STATUS_EVENTCOUNT_RESET]
			events |= 1 << self.EVENT_RESET
		if self.__eventCountParErr != self.__shmStatus[self.STATUS_EVENTCOUNT_PARERR]:
			self.__eventCountParErr = self.__shmStatus[self.STATUS_EVENTCOUNT_PARERR]
			events |= 1 << self.EVENT_PARERR
		if self.__eventCountNoMagic != self.__shmStatus[self.STATUS_EVENTCOUNT_NOMAGIC]:
			self.__eventCountNoMagic = self.__shmStatus[self.STATUS_EVENTCOUNT_NOMAGIC]
			events |= 1 << self.EVENT_NOMAGIC
		if self.__eventCountInvalLen != self.__shmStatus[self.STATUS_EVENTCOUNT_INVALLEN]:
			self.__eventCountInvalLen = self.__shmStatus[self.STATUS_EVENTCOUNT_INVALLEN]
			events |= 1 << self.EVENT_INVALLEN
		if self.__eventCountPBLenErr != self.__shmStatus[self.STATUS_EVENTCOUNT_PBLENERR]:
			self.__eventCountPBLenErr = self.__shmStatus[self.STATUS_EVENTCOUNT_PBLENERR]
			events |= 1 << self.EVENT_PBLENERR
		return events

class FpgaPhyDriver(object):
	"""Driver for FPGA based PROFIBUS PHY.
	"""

	FPGA_CLK_HZ = 16000000
	PING_INTERVAL = 0.1

	def __init__(self, spiDev=0, spiChipSelect=0, spiSpeedHz=1000000):
		self.__ioProc = None
		self.__nextPing = monotonic_time()
		self.__receivedPong = False
		self.__startup(spiDev, spiChipSelect, spiSpeedHz)

	def __startup(self, spiDev, spiChipSelect, spiSpeedHz):
		"""Startup the driver.
		"""
		self.shutdown()

		# Start the communication process.
		self.__ioProc = FpgaPhyProc(spiDev, spiChipSelect, spiSpeedHz)
		if not self.__ioProc.start():
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

	def __ping(self, tries=3, shutdown=True):
		"""Ping the FPGA and check if a pong can be received.
		Calls shutdown() and raises a FpgaPhyError on failure.
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
					if shutdown:
						try:
							self.shutdown()
						except FpgaPhyError as e:
							pass
					raise e

	def __fetchStatus(self):
		"""Fetch the FPGA status.
		"""
		txMsg = FpgaPhyMsgCtrl(FpgaPhyMsgCtrl.SPICTRL_GETSTATUS)
		rxMsg = self.__controlTransferSync(txMsg, FpgaPhyMsgCtrl.SPICTRL_STATUS)
		if not rxMsg:
			raise FpgaPhyError("Failed to get status.")
		return txMsg.ctrlData

	def shutdown(self):
		"""Shutdown the driver.
		"""
		if self.__ioProc is None:
			return
		self.__ioProc.shutdownProc()
		self.__ioProc = None

	def setBaudRate(self, baudrate):
		"""Configure the PHY baud rate.
		"""
		if self.__ioProc is None:
			raise FpgaPhyError("Cannot set baud rate. "
					    "Driver not initialized.")
		if baudrate < 9600 or baudrate > 12000000:
			raise FpgaPhyError("Invalid baud rate %d." % baudrate)

		clksPerSym = int(round(self.FPGA_CLK_HZ / baudrate))
		assert(1 <= clksPerSym <= 0xFFFFFF)
		#TODO calculate the baud rate error and reject if too big.

		txMsg = FpgaPhyMsgCtrl(FpgaPhyMsgCtrl.SPICTRL_BAUD,
					ctrlData=clksPerSym)
		rxMsg = self.__controlTransferSync(txMsg, FpgaPhyMsgCtrl.SPICTRL_BAUD)
		if not rxMsg or rxMsg.ctrlData != txMsg.ctrlData:
			raise FpgaPhyError("Failed to set baud rate.")

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
		return self.__ioProc.controlSend(ctrlMsg)

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
			raise FpgaPhyError("Reset detected. "
					   "Status = 0x%02X." % statusBits)
		if events & (1 << FpgaPhyProc.EVENT_NEWSTAT):
			statusBits = self.__fetchStatus()
			print("STAT 0x%X" % statusBits)
			pass#TODO
		if events & (1 << FpgaPhyProc.EVENT_PARERR):
			print("PARITY ERROR")
			pass#TODO
		if events & (1 << FpgaPhyProc.EVENT_NOMAGIC):
			print("MAGIC BYTE NOT FOUND")
			pass#TODO
		if events & (1 << FpgaPhyProc.EVENT_INVALLEN):
			print("INVALID LENGTH FIELD")
			pass#TODO
		if events & (1 << FpgaPhyProc.EVENT_PBLENERR):
			print("INVALID PROFIBUS TELEGRAM LENGTH")
			pass#TODO

	def telegramSend(self, txTelegramData):
		"""Send a PROFIBUS telegram.
		"""
		now = monotonic_time()
		if now >= self.__nextPing:
			if not self.__receivedPong:
				# We did not receive the PONG to the previous PING.
				raise FpgaPhyError("PING failed.")
			self.__nextPing = now + self.PING_INTERVAL
			self.__receivedPong = False
			# Send a PING to the FPGA to check if it is still alive.
			pingMsg = FpgaPhyMsgCtrl(FpgaPhyMsgCtrl.SPICTRL_PING)
			self.__controlSend(pingMsg)
		return self.__ioProc.dataSend(txTelegramData)

	def telegramReceive(self):
		"""Get a list of received PROFIBUS telegrams.
		Returns a list of bytes.
		The returned list might be empty.
		"""
		rxTelegrams = []
		ioProc = self.__ioProc
		events = ioProc.getEventStatus()
		if events:
			self.__nextPing = monotonic_time() + self.PING_INTERVAL
			self.__handleEvents(events)
		if ioProc.controlAvailable():
			self.__nextPing = monotonic_time() + self.PING_INTERVAL
			self.__handleControl()
		if ioProc.dataAvailable():
			self.__nextPing = monotonic_time() + self.PING_INTERVAL
			rxTelegrams = ioProc.dataReceive()
		return rxTelegrams
