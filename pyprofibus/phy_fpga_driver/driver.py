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


__all__ = [
	"ProfiPHYDriver",
	"ProfiPHYError",
]


class ProfiPHYError(Exception):
	pass

class ProfiPHYMsg(object):
	SPI_MS_MAGIC	= 0xAA
	SPI_SM_MAGIC	= 0x55

	PADDING		= 0x00
	PADDING_BYTE	= bytes([PADDING])

	SPI_FLG_START	= 0
	SPI_FLG_CTRL	= 1
	SPI_FLG_NEWSTAT	= 2 #TODO
	SPI_FLG_RESET	= 3 #TODO
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

class ProfiPHYMsgCtrl(ProfiPHYMsg):
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
				self.SPICTRL_RESULT	: "RESULT",
			}[self.ctrl]
		except KeyError as e:
			name = "%02X" % self.ctrl
		return "PHYControl(%s, 0x%08X)" % (name, self.ctrlData)

class ProfiPHYProc(multiprocessing.Process):
	STATUS_RUNNING		= 0
	STATUS_STOP		= 1
	STATUS_ERROR		= 2
	STATUS_CTRL_TXCOUNT	= 3
	STATUS_CTRL_RXCOUNT	= 4
	STATUS_DATA_TXCOUNT	= 5
	STATUS_DATA_RXCOUNT	= 6

	ERROR_NONE		= 0
	ERROR_OSERROR		= 1
	ERROR_PERMISSION	= 2

	META_OFFS_LO		= 0
	META_OFFS_HI		= 1
	META_LEN		= 2
	METASTRUCT_SIZE		= 3

	def __init__(self, spiDev, spiChipSelect, spiSpeedHz):
		super(ProfiPHYProc, self).__init__()

		self.__rxDataCount = 0
		self.__rxCtrlCount = 0
		self.__txDataCount = 0
		self.__txCtrlCount = 0
		self.__txDataWrOffs = 0
		self.__txCtrlWrOffs = 0

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
		super(ProfiPHYProc, self).start()
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

	def __ioProcMainLoop(self, spi):
		ctrlWrOffs = 0
		dataWrOffs = 0

		txDataCount = 0
		txCtrlCount = 0

		expectedRxLength = 0
		collectedRxLength = 0
		rxDataBuf = bytearray()

		shmMask = self.__shmMask

		CTRL_LEN = ProfiPHYMsgCtrl.CTRL_LEN
		RX_DATA_LEN = 11

		MIN_XFER_LEN = RX_DATA_LEN

		tailData = b""
		while not self.__shmStatus[self.STATUS_STOP]:
			txData = b""

			# Get the TX control data, if any.
			if txCtrlCount != self.__shmStatus[self.STATUS_CTRL_TXCOUNT]:
				ctrlRdOffs = (txCtrlCount * CTRL_LEN) & shmMask

				# Get the TX control message.
				txData = bytearray(CTRL_LEN)
				for i in range(CTRL_LEN):
					txData[i] = self.__shmTxCtrl[(ctrlRdOffs + i) & shmMask]

				txCtrlCount = (txCtrlCount + 1) & 0xFF
			# Get the PB TX data, if any.
			elif txDataCount != self.__shmStatus[self.STATUS_DATA_TXCOUNT]:
				metaBegin = txDataCount * self.METASTRUCT_SIZE
				dataRdOffs = self.__shmTxDataMeta[(metaBegin + self.META_OFFS_LO) & shmMask]
				dataRdOffs |= self.__shmTxDataMeta[(metaBegin + self.META_OFFS_HI) & shmMask] << 8
				dataRdLen = self.__shmTxDataMeta[(metaBegin + self.META_LEN) & shmMask]

				# Construct the TX data message.
				txData = bytearray(dataRdLen + 2)
				txData[0] = ProfiPHYMsg.SPI_MS_MAGIC
				txData[1] = 1 << ProfiPHYMsg.SPI_FLG_START
				txData[1] |= ProfiPHYMsg.parity(txData[1]) << ProfiPHYMsg.SPI_FLG_PARITY
				for i in range(dataRdLen):
					txData[i + 2] = self.__shmTxData[(dataRdOffs + i) & shmMask]

				txDataCount = (txDataCount + 1) & 0xFF

			# Pad the TX data, if required.
			if len(txData) < MIN_XFER_LEN:
				txData += ProfiPHYMsg.PADDING_BYTE * (MIN_XFER_LEN - len(txData))

			# Run the SPI transfer (transmit and receive).
			rxData = bytes(spi.xfer2(txData))
			# If we have tail data, prepend it to the received data.
			if tailData:
				rxData = tailData + rxData
				tailData = b""

			# Strip all leading padding bytes.
			rxData = rxData.lstrip(ProfiPHYMsg.PADDING_BYTE)
			if not rxData:
				continue

			# The first byte must be the magic byte.
			if rxData[0] != ProfiPHYMsg.SPI_SM_MAGIC:
				# Magic mismatch. Try to find the magic byte.
				rxData = rxData[1:]
				while rxData and rxData[0] != ProfiPHYMsg.SPI_SM_MAGIC:
					rxData = rxData[1:]
				if not rxData:
					# Magic byte not found.
					continue

			# If the remaining data is not enough, get more bytes.
			if len(rxData) < 3:
				rxData += bytes(spi.xfer2(ProfiPHYMsg.PADDING_BYTE * (3 - len(rxData))))

			# Get and check the received flags field.
			flgField = rxData[1]
			if ProfiPHYMsg.parity(flgField):
				# Parity mismatch.
				continue

			if flgField & (1 << ProfiPHYMsg.SPI_FLG_CTRL):
				# Received control message
				if len(rxData) < CTRL_LEN:
					rxData += bytes(spi.xfer2(ProfiPHYMsg.PADDING_BYTE * (CTRL_LEN - len(rxData))))

				# Write the control message to SHM.
				for i in range(CTRL_LEN):
					self.__shmRxCtrl[(ctrlWrOffs + i) & shmMask] = rxData[i]
				ctrlWrOffs = (ctrlWrOffs + CTRL_LEN) & shmMask

				# Update the receive count in SHM.
				count = self.__shmStatus[self.STATUS_CTRL_RXCOUNT]
				self.__shmStatus[self.STATUS_CTRL_RXCOUNT] = (count + 1) & 0xFF

				# If there is data left, add it to tail data.
				tailData = rxData[CTRL_LEN : ]
			else:
				# Received data message
				if len(rxData) < RX_DATA_LEN:
					rxData += bytes(spi.xfer2(ProfiPHYMsg.PADDING_BYTE * (RX_DATA_LEN - len(rxData))))

				# If this is a telegram start, clear the temp RX buffers.
				if flgField & (1 << ProfiPHYMsg.SPI_FLG_START):
					expectedRxLength = 0
					collectedRxLength = 0
					rxDataBuf = bytearray()

				# Get the raw PB data.
				rawDataLen = rxData[10]
				if rawDataLen <= 0 or rawDataLen > 8:
					# Invalid length.
					continue
				rawData = rxData[2 : 2 + rawDataLen]
				rxDataBuf += rawData

				# If we don't know the PB telegram length, try to calculate it.
				if expectedRxLength <= 0:
					telegramLen = ProfiPHYMsg.calcLen(rxDataBuf)
					if (telegramLen == ProfiPHYMsg.LEN_ERROR or
					    telegramLen == ProfiPHYMsg.LEN_UNKNOWN):
						# Could not determine telegram length.
						continue
					if telegramLen == ProfiPHYMsg.LEN_NEEDMORE:
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
					self.__shmStatus[self.STATUS_DATA_RXCOUNT] = (count + 1) & 0xFF

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
		CTRL_LEN = ProfiPHYMsgCtrl.CTRL_LEN
		shmMask = self.__shmMask
		newCount = self.__shmStatus[self.STATUS_CTRL_RXCOUNT]
		rxCount = self.__rxCtrlCount
		while rxCount != newCount:
			ctrlRdOffs = (rxCount * CTRL_LEN) & shmMask
			rxCtrl = bytearray(CTRL_LEN)
			for i in range(CTRL_LEN):
				rxCtrl[i] = self.__shmRxCtrl[(ctrlRdOffs + i) & shmMask]
			rxCtrlMsgs.append(ProfiPHYMsgCtrl.fromBytes(rxCtrl))

			rxCount = (rxCount + 1) & 0xFF
		self.__rxCtrlCount = rxCount
		return rxCtrlMsgs

class ProfiPHYDriver(object):
	"""Driver for FPGA based PROFIBUS PHY.
	"""

	FPGA_CLK_HZ = 16000000

	def __init__(self, spiDev=0, spiChipSelect=0, spiSpeedHz=1000000):
		self.__ioProc = None
		self.__startup(spiDev, spiChipSelect, spiSpeedHz)

	def __startup(self, spiDev, spiChipSelect, spiSpeedHz):
		"""Startup the driver.
		"""
		self.shutdown()

		# Start the communication process.
		self.__ioProc = ProfiPHYProc(spiDev, spiChipSelect, spiSpeedHz)
		if not self.__ioProc.start():
			raise ProfiPHYError("Failed to start I/O process.")

		# Reset the FPGA.
		# But first ping the device to make sure SPI communication works.
		self.__ping()
		self.__controlSend(ProfiPHYMsgCtrl(ProfiPHYMsgCtrl.SPICTRL_SOFTRESET))
		time.sleep(0.01)
		self.__ping()

	def __ping(self, tries=3, shutdown=True):
		"""Ping the FPGA and check if a pong can be received.
		Calls shutdown() and raises a ProfiPHYError on failure.
		"""
		for i in range(tries - 1, -1, -1):
			try:
				pingMsg = ProfiPHYMsgCtrl(ProfiPHYMsgCtrl.SPICTRL_PING)
				pongMsg = self.__controlTransferSync(pingMsg,
							ProfiPHYMsgCtrl.SPICTRL_PONG)
				if not pongMsg:
					raise ProfiPHYError("Cannot communicate with "
							    "FPGA PHY. Timeout.")
				break
			except ProfiPHYError as e:
				if i <= 0:
					if shutdown:
						try:
							self.shutdown()
						except ProfiPHYError as e:
							pass
					raise e

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
			raise ProfiPHYError("Cannot set baud rate. "
					    "Driver not initialized.")
		if baudrate < 9600 or baudrate > 12000000:
			raise ProfiPHYError("Invalid baud rate %d." % baudrate)

		clksPerSym = int(round(self.FPGA_CLK_HZ / baudrate))
		assert(1 <= clksPerSym <= 0xFFFFFF)
		#TODO calculate the baud rate error and reject if too big.

		txMsg = ProfiPHYMsgCtrl(ProfiPHYMsgCtrl.SPICTRL_BAUD,
					ctrlData=clksPerSym)
		rxMsg = self.__controlTransferSync(txMsg, ProfiPHYMsgCtrl.SPICTRL_BAUD)
		if not rxMsg or rxMsg.ctrlData != txMsg.ctrlData:
			raise ProfiPHYError("Failed to set baud rate.")

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
		"""Send a ProfiPHYMsgCtrl() control message.
		"""
		return self.__ioProc.controlSend(ctrlMsg)

	def __controlReceive(self):
		"""Get a list of received control messages.
		Returns a list of ProfiPHYMsgCtrl().
		The returned list might be empty.
		"""
		return self.__ioProc.controlReceive()

	def telegramSend(self, txTelegramData):
		"""Send a PROFIBUS telegram.
		"""
		return self.__ioProc.dataSend(txTelegramData)

	def telegramReceive(self):
		"""Get a list of received PROFIBUS telegrams.
		Returns a list of bytes.
		The returned list might be empty.
		"""
		return self.__ioProc.dataReceive()
