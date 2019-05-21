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

from pyprofibus.phy_fpga_driver.messages import *

import multiprocessing
import mmap
import spidev
import time
import sys


__all__ = [
	"FpgaPhyProc",
]


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
						expectedRxLength = 0
						collectedRxLength = 0
						rxDataBuf = bytearray()
						self.__incShmStatus(self.STATUS_EVENTCOUNT_PBLENERR)
						continue
					if telegramLen == FpgaPhyMsg.LEN_NEEDMORE:
						# Need more telegram bytes.
						continue
					expectedRxLength = telegramLen

				# If we know the PB telegram length, check if we have enough data.
				if (expectedRxLength > 0 and
				    len(rxDataBuf) >= expectedRxLength):

					if len(rxDataBuf) > expectedRxLength:
						# We got too much data.
						self.__incShmStatus(self.STATUS_EVENTCOUNT_INVALLEN)

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
