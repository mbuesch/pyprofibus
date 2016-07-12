# -*- coding: utf-8 -*-
#
# PROFIBUS - Layer 2 - Fieldbus Data Link (FDL)
#
# Copyright (c) 2013-2016 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus.compat import *

from pyprofibus.phy import *
from pyprofibus.util import *


class FdlError(ProfibusError):
	pass


class FdlFCB():
	"""FCB context, per slave.
	"""

	def __init__(self, enable = False):
		self.resetFCB()
		self.enableFCB(enable)

	def resetFCB(self):
		self.__fcb = 1
		self.__fcv = 0
		self.__fcbWaitingReply = False

	def enableFCB(self, enabled = True):
		self.__fcbEnabled = bool(enabled)

	def FCBnext(self):
		self.__fcb ^= 1
		self.__fcv = 1
		self.__fcbWaitingReply = False

	def enabled(self):
		return self.__fcbEnabled

	def bitIsOn(self):
		return self.__fcb != 0

	def bitIsValid(self):
		return self.__fcv != 0

	def setWaitingReply(self):
		self.__fcbWaitingReply = True

	def handleReply(self):
		if self.__fcbWaitingReply:
			self.FCBnext()

	def __repr__(self):
		return "FdlFCB(en=%s, fcb=%d, fcv=%d, wait=%s)" % (
			str(self.__fcbEnabled), self.__fcb,
			self.__fcv, str(self.__fcbWaitingReply))

class FdlTransceiver(object):
	def __init__(self, phy):
		self.phy = phy
		self.setRXFilter(None)

	def setRXFilter(self, newFilter):
		if newFilter is None:
			newFilter = range(0, FdlTelegram.ADDRESS_MASK + 1)
		self.__rxFilter = set(newFilter)

	def __checkRXFilter(self, telegram):
		if telegram.da is None:
			# Accept telegrams without DA field.
			return True
		# Accept the packet, if it's in the RX filter.
		return (telegram.da & FdlTelegram.ADDRESS_MASK) in self.__rxFilter

	def poll(self, timeout=0):
		ok, telegram = False, None
		reply = self.phy.poll(timeout)
		if reply is not None:
			telegram = FdlTelegram.fromRawData(reply)
			if self.__checkRXFilter(telegram):
				ok = True
		return (ok, telegram)

	# Send an FdlTelegram.
	def send(self, fcb, telegram):
		srd = False
		if telegram.fc & FdlTelegram.FC_REQ:
			func = telegram.fc & FdlTelegram.FC_REQFUNC_MASK
			srd = func in (FdlTelegram.FC_SRD_LO,
				       FdlTelegram.FC_SRD_HI,
				       FdlTelegram.FC_SDA_LO,
				       FdlTelegram.FC_SDA_HI,
				       FdlTelegram.FC_DDB,
				       FdlTelegram.FC_FDL_STAT,
				       FdlTelegram.FC_IDENT,
				       FdlTelegram.FC_LSAP)
			telegram.fc &= ~(FdlTelegram.FC_FCB | FdlTelegram.FC_FCV)
			if fcb.enabled():
				if fcb.bitIsOn():
					telegram.fc |= FdlTelegram.FC_FCB
				if fcb.bitIsValid():
					telegram.fc |= FdlTelegram.FC_FCV
				if srd:
					fcb.setWaitingReply()
				else:
					fcb.FCBnext()
		self.phy.send(telegram.getRawData(), srd)

class FdlTelegram(object):
	# Start delimiter
	SD1		= 0x10	# No DU
	SD2		= 0x68	# Variable DU
	SD3		= 0xA2	# 8 octet fixed DU
	SD4		= 0xDC	# Token telegram
	SC		= 0xE5	# Short ACK

	# End delimiter
	ED		= 0x16

	# Addresses
	ADDRESS_MASK	= 0x7F	# Address value mask
	ADDRESS_EXT	= 0x80	# DAE/SAE present

	ADDRESS_MCAST	= 127	# Multicast/broadcast address

	# DAE/SAE (Address extension)
	AE_EXT		= 0x80	# Further extensions present
	AE_SEGMENT	= 0x40	# Segment address
	AE_ADDRESS	= 0x3F	# Address extension number

	# Frame Control
	FC_REQ		= 0x40	# Request

	# Request Frame Control function codes (FC_REQ set)
	FC_REQFUNC_MASK	= 0x0F
	FC_TIME_EV	= 0x00	# Time event
	FC_SDA_LO	= 0x03	# SDA low prio
	FC_SDN_LO	= 0x04	# SDN low prio
	FC_SDA_HI	= 0x05	# SDA high prio
	FC_SDN_HI	= 0x06	# SDN high prio
	FC_DDB		= 0x07	# Req. diagnosis data
	FC_FDL_STAT	= 0x09	# Req. FDL status
	FC_TE		= 0x0A	# Actual time event
	FC_CE		= 0x0B	# Actual counter event
	FC_SRD_LO	= 0x0C	# SRD low prio
	FC_SRD_HI	= 0x0D	# SRD high prio
	FC_IDENT	= 0x0E	# Req. ident
	FC_LSAP		= 0x0F	# Req. LSAP status

	# Frame Control Frame Count Bit (FC_REQ set)
	FC_FCV		= 0x10	# Frame Count Bit valid
	FC_FCB		= 0x20	# Frame Count Bit

	# Response Frame Control function codes (FC_REQ clear)
	FC_RESFUNC_MASK	= 0x0F
	FC_OK		= 0x00	# Positive ACK
	FC_UE		= 0x01	# User error
	FC_RR		= 0x02	# Resource error
	FC_RS		= 0x03	# No service activated
	FC_DL		= 0x08	# Res. data low
	FC_NR		= 0x09	# ACK negative
	FC_DH		= 0x0A	# Res. data high
	FC_RDL		= 0x0C	# Res. data low, resource error
	FC_RDH		= 0x0D	# Res. data high, resource error

	# Response Frame Control Station Type (FC_REQ clear)
	FC_STYPE_MASK	= 0x30
	FC_SLAVE	= 0x00	# Slave station
	FC_MNRDY	= 0x10	# Master, not ready to enter token ring
	FC_MRDY		= 0x20	# Master, ready to enter token ring
	FC_MTR		= 0x30	# Master, in token ring

	@classmethod
	def getSizeFromRaw(cls, data):
		try:
			sd = data[0]
			try:
				return {
					cls.SD1	: 6,
					cls.SD3	: 14,
					cls.SD4	: 3,
					cls.SC	: 1,
				}[sd]
			except KeyError:
				pass
			if sd == cls.SD2:
				le = data[1]
				if data[2] != le:
					raise FdlError("Repeated length field mismatch")
				if le < 3 or le > 249:
					raise FdlError("Invalid LE field")
				return le + 6
			raise FdlError("Unknown start delimiter: %02X" % sd)
		except IndexError:
			raise FdlError("Invalid FDL packet format")

	def __init__(self, sd, haveLE=False, da=None, sa=None,
		     fc=None, dae=(), sae=(), du=None,
		     haveFCS=False, ed=None):
		self.sd = sd
		self.haveLE = haveLE
		self.da = (da & FdlTelegram.ADDRESS_MASK) if da is not None else None
		self.sa = (sa & FdlTelegram.ADDRESS_MASK) if sa is not None else None
		self.fc = fc
		self.dae = dae
		self.sae = sae
		self.du = du
		self.haveFCS = haveFCS
		self.ed = ed
		if self.haveLE:
			assert(self.du is not None)

	def __repr__(self):
		def sdVal(val):
			try:
				return {
					FdlTelegram.SD1	: "SD1",
					FdlTelegram.SD2	: "SD2",
					FdlTelegram.SD3	: "SD3",
					FdlTelegram.SD4	: "SD4",
					FdlTelegram.SC	: "SC",
				}[val]
			except KeyError:
				return intToHex(val)
		return "FdlTelegram(sd=%s, haveLE=%s, da=%s, sa=%s, " \
			"fc=%s, dae=%s, sae=%s, du=%s, haveFCS=%s, ed=%s)" %\
			(sdVal(self.sd), boolToStr(self.haveLE),
			 intToHex(self.da), intToHex(self.sa),
			 intToHex(self.fc),
			 intListToHex(self.dae),
			 intListToHex(self.sae),
			 intListToHex(self.du),
			 boolToStr(self.haveFCS), intToHex(self.ed))

	# Get real length of DU field
	def getRealDuLen(self):
		return len(self.du) + len(self.dae) + len(self.sae)

	@staticmethod
	def calcFCS(data):
		return sum(data) & 0xFF

	def getRawData(self):
		data = []
		if self.haveLE:
			le = 3 + self.getRealDuLen()
			data.extend([self.sd, le, le])
		data.append(self.sd)
		if self.da is not None:
			data.append((self.da | FdlTelegram.ADDRESS_EXT) if self.dae
				    else self.da)
		if self.sa is not None:
			data.append((self.sa | FdlTelegram.ADDRESS_EXT) if self.sae
				    else self.sa)
		if self.fc is not None:
			data.append(self.fc)
		data.extend(self.dae)
		data.extend(self.sae)
		if self.du is not None:
			data.extend(self.du)
		if self.haveFCS:
			if self.haveLE:
				fcs = self.calcFCS(data[4:])
			else:
				fcs = self.calcFCS(data[1:])
			data.append(fcs)
		if self.ed is not None:
			data.append(self.ed)
		return data

	# Extract address extension bytes from DU
	@staticmethod
	def __duExtractAe(du):
		ae = []
		while 1:
			if not du:
				raise FdlError("Address extension error: Data too short")
			aeByte = du[0]
			ae.append(aeByte)
			du = du[1:]
			if not aeByte & FdlTelegram.AE_EXT:
				break
		return (du, ae)

	@staticmethod
	def fromRawData(data):
		error = False
		try:
			sd = data[0]
			if sd == FdlTelegram.SD1:
				# No DU
				if len(data) != 6:
					raise FdlError("Invalid FDL packet length")
				if data[5] != FdlTelegram.ED:
					raise FdlError("Invalid end delimiter")
				if data[4] != FdlTelegram.calcFCS(data[1:4]):
					raise FdlError("Checksum mismatch")
				return FdlTelegram_stat0(
					da=data[1], sa=data[2], fc=data[3])
			elif sd == FdlTelegram.SD2:
				# Variable DU
				le = data[1]
				if data[2] != le:
					raise FdlError("Repeated length field mismatch")
				if le < 3 or le > 249:
					raise FdlError("Invalid LE field")
				if data[3] != sd:
					raise FdlError("Repeated SD mismatch")
				if data[5+le] != FdlTelegram.ED:
					raise FdlError("Invalid end delimiter")
				if data[4+le] != FdlTelegram.calcFCS(data[4:4+le]):
					raise FdlError("Checksum mismatch")
				du = data[7:7+(le-3)]
				if len(du) != le - 3:
					raise FdlError("FDL packet shorter than FE")
				da, sa, dae, sae = data[4], data[5], [], []
				if da & FdlTelegram.ADDRESS_EXT:
					du, dae = FdlTelegram.__duExtractAe(du)
				if sa & FdlTelegram.ADDRESS_EXT:
					du, sae = FdlTelegram.__duExtractAe(du)
				return FdlTelegram_var(
					da=da, sa=sa, fc=data[6], dae=dae, sae=sae, du=du)
			elif sd == FdlTelegram.SD3:
				# Static 8 byte DU
				if len(data) != 14:
					raise FdlError("Invalid FDL packet length")
				if data[13] != FdlTelegram.ED:
					raise FdlError("Invalid end delimiter")
				if data[12] != FdlTelegram.calcFCS(data[1:12]):
					raise FdlError("Checksum mismatch")
				du = data[4:12]
				da, sa, dae, sae = data[1], data[2], [], []
				if da & FdlTelegram.ADDRESS_EXT:
					du, dae = FdlTelegram.__duExtractAe(du)
				if sa & FdlTelegram.ADDRESS_EXT:
					du, sae = FdlTelegram.__duExtractAe(du)
				return FdlTelegram_stat8(
					da=da, sa=sa, fc=data[3], dae=dae, sae=sae, du=du)
			elif sd == FdlTelegram.SD4:
				# Token telegram
				if len(data) != 3:
					raise FdlError("Invalid FDL packet length")
				return FdlTelegram_token(
					da=data[1], sa=data[2])
			elif sd == FdlTelegram.SC:
				# ACK
				if len(data) != 1:
					raise FdlError("Invalid FDL packet length")
				return FdlTelegram_ack()
			else:
				raise FdlError("Invalid start delimiter")
		except IndexError:
			error = True
		if error:
			raise FdlError("Invalid FDL packet format")

	@classmethod
	def checkType(cls, telegram):
		return isinstance(telegram, cls)

class FdlTelegram_var(FdlTelegram):
	def __init__(self, da, sa, fc, dae, sae, du):
		FdlTelegram.__init__(self, sd=FdlTelegram.SD2,
			haveLE=True, da=da, sa=sa, fc=fc,
			dae=dae, sae=sae, du=du,
			haveFCS=True, ed=FdlTelegram.ED)
		if self.getRealDuLen() > 246:
			raise FdlError("Invalid data length (> 246)")

class FdlTelegram_stat8(FdlTelegram):
	def __init__(self, da, sa, fc, dae, sae, du):
		FdlTelegram.__init__(self, sd=FdlTelegram.SD3,
			da=da, sa=sa, fc=fc,
			dae=dae, sae=sae, du=du,
			haveFCS=True, ed=FdlTelegram.ED)
		if self.getRealDuLen() != 8:
			raise FdlError("Invalid data length (!= 8)")

class FdlTelegram_stat0(FdlTelegram):
	def __init__(self, da, sa, fc):
		FdlTelegram.__init__(self, sd=FdlTelegram.SD1,
			da=da, sa=sa, fc=fc,
			haveFCS=True, ed=FdlTelegram.ED)

class FdlTelegram_token(FdlTelegram):
	def __init__(self, da, sa):
		FdlTelegram.__init__(self, sd=FdlTelegram.SD4,
			da=da, sa=sa)

class FdlTelegram_ack(FdlTelegram):
	def __init__(self):
		FdlTelegram.__init__(self, sd=FdlTelegram.SC)

class FdlTelegram_FdlStat_Req(FdlTelegram_stat0):
	def __init__(self, da, sa):
		FdlTelegram_stat0.__init__(self, da=da, sa=sa,
			fc=FdlTelegram.FC_REQ |\
			   FdlTelegram.FC_FDL_STAT)

class FdlTelegram_FdlStat_Con(FdlTelegram_stat0):
	def __init__(self, da, sa,
		     fc=FdlTelegram.FC_OK |
		        FdlTelegram.FC_SLAVE):
		FdlTelegram_stat0.__init__(self, da=da, sa=sa, fc=fc)

class FdlTelegram_Ident_Req(FdlTelegram_stat0):
	def __init__(self, da, sa):
		FdlTelegram_stat0.__init__(self, da=da, sa=sa,
			fc=FdlTelegram.FC_REQ |\
			   FdlTelegram.FC_IDENT)

class FdlTelegram_Lsap_Req(FdlTelegram_stat0):
	def __init__(self, da, sa):
		FdlTelegram_stat0.__init__(self, da=da, sa=sa,
			fc=FdlTelegram.FC_REQ |\
			   FdlTelegram.FC_LSAP)
