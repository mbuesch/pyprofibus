# -*- coding: utf-8 -*-
#
# PROFIBUS DP - Layer 7
#
# Copyright (c) 2013-2016 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus.compat import *

from pyprofibus.fdl import *
from pyprofibus.util import *


class DpError(ProfibusError):
	pass

class DpTransceiver(object):
	def __init__(self, fdlTrans, thisIsMaster):
		self.fdlTrans = fdlTrans
		self.thisIsMaster = thisIsMaster

	def poll(self, timeout = 0):
		retTelegram = None
		ok, fdlTelegram = self.fdlTrans.poll(timeout)
		if ok and fdlTelegram:
			if fdlTelegram.sd in {FdlTelegram.SD1,
					      FdlTelegram.SD2,
					      FdlTelegram.SD3}:
				retTelegram = DpTelegram.fromFdlTelegram(
						fdlTelegram, self.thisIsMaster)
			elif fdlTelegram.sd in {FdlTelegram.SC,
						FdlTelegram.SD4}:
				retTelegram = fdlTelegram
			else:
				ok = False
		return (ok, retTelegram)

	# Send a DpTelegram.
	def send(self, fcb, telegram):
		self.fdlTrans.send(fcb, telegram.toFdlTelegram())

class DpTelegram(object):
	# Source Service Access Point number
	SSAP_MS2		= 50	# DPM2 to slave
	SSAP_MS1		= 51	# DPM1 to slave
	SSAP_MM			= 54	# Master to master
	SSAP_MS0		= 62	# Master to slave

	# Destination Service Access Point number
	DSAP_RESOURCE_MAN	= 49
	DSAP_ALARM		= 50
	DSAP_SERVER		= 51
	DSAP_EXT_USER_PRM	= 53
	DSAP_SET_SLAVE_ADR	= 55
	DSAP_RD_INP		= 56
	DSAP_RD_OUTP		= 57
	DSAP_GLOBAL_CONTROL	= 58
	DSAP_GET_CFG		= 59
	DSAP_SLAVE_DIAG		= 60
	DSAP_SET_PRM		= 61
	DSAP_CHK_CFG		= 62

	def __init__(self, da, sa, fc, dsap=None, ssap=None):
		self.da = da
		self.sa = sa
		self.fc = fc
		self.dsap = dsap
		self.ssap = ssap

	def __repr__(self):
		return "DpTelegram(da=%s, sa=%s, fc=%s, " \
			"dsap=%s, ssap=%s) => %s" %\
			(intToHex(self.da), intToHex(self.sa),
			 intToHex(self.fc), intToHex(self.dsap),
			 intToHex(self.ssap),
			 str(self.getDU()))

	def toFdlTelegram(self):
		du = self.getDU()

		dae, sae = [], []
		if self.dsap is not None:
			dae.append(self.dsap)
		if self.ssap is not None:
			sae.append(self.ssap)

		le = len(du) + len(dae) + len(sae)
		if le == 0:
			return FdlTelegram_stat0(
				da=self.da, sa=self.sa, fc=self.fc)
		elif le == 8:
			return FdlTelegram_stat8(
				da=self.da, sa=self.sa, fc=self.fc,
				dae=dae, sae=sae, du=du)
		else:
			return FdlTelegram_var(
				da=self.da, sa=self.sa, fc=self.fc,
				dae=dae, sae=sae, du=du)

	# Extract the SSAP/DSAP from SAE/DAE
	@classmethod
	def extractSAP(cls, ae):
		if ae:
			for aeByte in ae:
				if not (aeByte & 0x40):
					return aeByte & 0x3F
		return None

	# Extract the segment address from SAE/DAE
	@classmethod
	def extractSegmentAddr(cls, ae):
		if ae:
			for aeByte in ae:
				if aeByte & 0x40:
					return aeByte & 0x3F
		return None

	# Create a DP telegram from an FDL telegram.
	# If thisIsMaster is True, the local station is a master.
	@classmethod
	def fromFdlTelegram(cls, fdl, thisIsMaster):
		dsap, ssap = cls.extractSAP(fdl.dae), cls.extractSAP(fdl.sae)

		# Handle telegrams without SSAP/DSAP
		if not dsap:
			if ssap:
				raise DpError("Telegram with SSAP, but without DSAP")
			if fdl.fc & FdlTelegram.FC_REQ:
				return DpTelegram_DataExchange_Req.fromFdlTelegram(fdl)
			else:
				return DpTelegram_DataExchange_Con.fromFdlTelegram(fdl)
		if not ssap:
			raise DpError("Telegram with DSAP, but without SSAP")

		# Handle telegrams with SSAP/DSAP
		if thisIsMaster:
			if dsap == DpTelegram.SSAP_MS0:
				if ssap == DpTelegram.DSAP_SLAVE_DIAG:
					return DpTelegram_SlaveDiag_Con.fromFdlTelegram(fdl)
				elif ssap == DpTelegram.DSAP_GET_CFG:
					return DpTelegram_GetCfg_Con.fromFdlTelegram(fdl)
				else:
					raise DpError("Unknown SSAP: %d" % ssap)
			else:
				raise DpError("Unknown DSAP: %d" % dsap)
		else:
			if ssap == DpTelegram.SSAP_MS0:
				if dsap == DpTelegram.DSAP_SLAVE_DIAG:
					return DpTelegram_SlaveDiag_Req.fromFdlTelegram(fdl)
				elif dsap == DpTelegram.DSAP_SET_PRM:
					return DpTelegram_SetPrm_Req.fromFdlTelegram(fdl)
				elif dsap == DpTelegram.DSAP_CHK_CFG:
					return DpTelegram_ChkCfg_Req.fromFdlTelegram(fdl)
				else:
					raise DpError("Unknown DSAP: %d" % dsap)
			else:
				raise DpError("Unknown SSAP: %d" % ssap)

	# Get Data-Unit.
	# This function is overloaded in subclasses.
	def getDU(self):
		return []

	@classmethod
	def checkType(cls, telegram):
		return isinstance(telegram, cls)

class _DataExchange_Common(DpTelegram):
	def __init__(self, da, sa, fc, du):
		DpTelegram.__init__(self,
			da=da, sa=sa, fc=fc)
		self.du = list(du[:])

	def appendData(self, data):
		if not self.du:
			self.du = []
		self.du.append(data)

	def getDU(self):
		return self.du[:]

	@classmethod
	def fromFdlTelegram(cls, fdl):
		dp = cls(da=fdl.da,
			 sa=fdl.sa,
			 fc=fdl.fc,
			 du=fdl.du if fdl.du else ())
		return dp

class DpTelegram_DataExchange_Req(_DataExchange_Common):
	def __init__(self, da, sa,
		     fc=FdlTelegram.FC_SRD_HI |
		        FdlTelegram.FC_REQ,
		     du=()):
		_DataExchange_Common.__init__(self,
			da=da, sa=sa, fc=fc, du=du)

class DpTelegram_DataExchange_Con(_DataExchange_Common):
	def __init__(self, da, sa,
		     fc=FdlTelegram.FC_DL,
		     du=()):
		_DataExchange_Common.__init__(self,
			da=da, sa=sa, fc=fc, du=du)

class DpTelegram_SlaveDiag_Req(DpTelegram):
	def __init__(self, da, sa,
		     fc=FdlTelegram.FC_SRD_HI |
		        FdlTelegram.FC_REQ,
		     dsap=DpTelegram.DSAP_SLAVE_DIAG,
		     ssap=DpTelegram.SSAP_MS0):
		DpTelegram.__init__(self, da=da, sa=sa, fc=fc,
				    dsap=dsap, ssap=ssap)

	@classmethod
	def fromFdlTelegram(cls, fdl):
		dp = cls(da=fdl.da,
			 sa=fdl.sa,
			 fc=fdl.fc,
			 dsap=cls.extractSAP(fdl.dae),
			 ssap=cls.extractSAP(fdl.sae))
		return dp

class DpTelegram_SlaveDiag_Con(DpTelegram):
	# Flags byte 0
	B0_STANOEX		= 0x01	# Station_Non_Existent
	B0_STANORDY		= 0x02	# Station_Not_Reay
	B0_CFGFLT		= 0x04	# Cfg_Fault
	B0_EXTDIAG		= 0x08	# Ext_Diag
	B0_NOSUPP		= 0x10	# Not_Supported
	B0_INVALSR		= 0x20	# Invalid_Slave_Response
	B0_PRMFLT		= 0x40	# Prm_Fault
	B0_MLOCK		= 0x80	# Master_Lock

	# Flags byte 1
	B1_PRMREQ		= 0x01	# Prm_Req
	B1_SDIAG		= 0x02	# Stat_Diag
	B1_ONE			= 0x04	# Always 1
	B1_WD			= 0x08	# Wd_On
	B1_FREEZE		= 0x10	# Freeze_Mode
	B1_SYNC			= 0x20	# Sync_Mode
	B1_RES			= 0x40	# Reserved
	B1_DEAC			= 0x80	# Deactivated

	# Flags byte 2
	B2_EXTDIAGOVR		= 0x80	# Ext_Diag_Overflow

	def __init__(self, da, sa, fc=FdlTelegram.FC_DL,
		     dsap=DpTelegram.SSAP_MS0,
		     ssap=DpTelegram.DSAP_SLAVE_DIAG):
		DpTelegram.__init__(self, da=da, sa=sa, fc=fc,
			dsap=dsap, ssap=ssap)
		self.b0 = 0
		self.b1 = 0
		self.b2 = 0
		self.masterAddr = 255
		self.identNumber = 0

	def __repr__(self):
		return "DpTelegram_SlaveDiag_Con(da=%s, sa=%s, fc=%s, " \
			"dsap=%s, ssap=%s) => " \
			"(b0=%s, b1=%s, b2=%s, masterAddr=%s, identNumber=%s)" %\
			(intToHex(self.da), intToHex(self.sa),
			 intToHex(self.fc),
			 intToHex(self.dsap), intToHex(self.ssap),
			 intToHex(self.b0), intToHex(self.b1), intToHex(self.b2),
			 intToHex(self.masterAddr), intToHex(self.identNumber))

	@classmethod
	def fromFdlTelegram(cls, fdl):
		dp = cls(da=fdl.da,
			 sa=fdl.sa,
			 fc=fdl.fc,
			 dsap=cls.extractSAP(fdl.dae),
			 ssap=cls.extractSAP(fdl.sae))
		try:
			dp.b0 = fdl.du[0]
			dp.b1 = fdl.du[1]
			dp.b2 = fdl.du[2]
			dp.masterAddr = fdl.du[3]
			dp.identNumber = (fdl.du[4] << 8) | fdl.du[5]
		except IndexError:
			raise DpError("Invalid Slave_Diag telegram format")
		return dp

	def getDU(self):
		return [self.b0, self.b1, self.b2,
			self.masterAddr,
			(self.identNumber >> 8) & 0xFF,
			self.identNumber & 0xFF]

	def notExist(self):
		return (self.b0 & self.B0_STANOEX) != 0

	def notReady(self):
		return (self.b0 & self.B0_STANORDY) != 0

	def cfgFault(self):
		return (self.b0 & self.B0_CFGFLT) != 0

	def hasExtDiag(self):
		return (self.b0 & self.B0_EXTDIAG) != 0

	def isNotSupp(self):
		return (self.b0 & self.B0_NOSUPP) != 0

	def prmFault(self):
		return (self.b0 & self.B0_PRMFLT) != 0

	def masterLock(self):
		return (self.b0 & self.B0_MLOCK) != 0

	def hasOnebit(self):
		return (self.b1 & self.B1_ONE) != 0

	def needsNewPrmCfg(self):
		return ((self.b0 & self.B0_CFGFLT) != 0 or\
			(self.b0 & self.B0_PRMFLT) != 0 or\
			(self.b1 & self.B1_PRMREQ) != 0)

	def isReadyDataEx(self):
		return not ((self.b0 & (\
			     self.B0_STANOEX |\
			     self.B0_STANORDY |\
			     self.B0_CFGFLT |\
			     self.B0_PRMFLT)) != 0 or\
			    (self.b1 & (\
			     self.B1_PRMREQ)) != 0)

class DpTelegram_SetPrm_Req(DpTelegram):
	# Station status
	STA_WD			= 0x08	# WD_On
	STA_FREEZE		= 0x10	# Freeze_Req
	STA_SYNC		= 0x20	# Sync_Req
	STA_UNLOCK		= 0x40	# Unlock_Req
	STA_LOCK		= 0x80	# Lock_Req

	# First DPv1 User_Prm_Data byte. (DPv1 or later only)
	DPV1PRM0_R0		= 0x01	# Reserved bit 0
	DPV1PRM0_R1		= 0x02	# Reserved bit 1
	DPV1PRM0_WD1MS		= 0x04	# 1 ms warchdog base.
	DPV1PRM0_R3		= 0x08	# Reserved bit 3
	DPV1PRM0_R4		= 0x10	# Reserved bit 4
	DPV1PRM0_PUBL		= 0x20	# Run as publisher
	DPV1PRM0_FAILSAFE	= 0x40	# Fail_Safe mode
	DPV1PRM0_V1MODE		= 0x80	# DPv1 mode enable

	# Second DPv1 User_Prm_Data byte. (DPv1 or later only)
	DPV1PRM1_REDCFG		= 0x01	# Reduced Chk_Cfg
	DPV1PRM1_R1		= 0x02	# Reserved bit 1
	DPV1PRM1_ALRMUPD	= 0x04	# Alarm: update
	DPV1PRM1_ALRMSTAT	= 0x08	# Alarm: status
	DPV1PRM1_ALRMVEND	= 0x10	# Alarm: vendor specific
	DPV1PRM1_ALRMDIAG	= 0x20	# Alarm: diagnostic
	DPV1PRM1_ALRMPROC	= 0x40	# Alarm: process
	DPV1PRM1_ALRMPLUG	= 0x80	# Alarm: pull-plug

	# Third DPv1 User_Prm_Data byte. (DPv1 or later only)
	DPV1PRM2_ALRMCNT_MASK	= 0x07	# Alarm count mask
	DPV1PRM2_ALRMCNT1	= 0x00	# 1 alarm in total
	DPV1PRM2_ALRMCNT2	= 0x01	# 2 alarms in total
	DPV1PRM2_ALRMCNT4	= 0x02	# 4 alarms in total
	DPV1PRM2_ALRMCNT8	= 0x03	# 8 alarms in total
	DPV1PRM2_ALRMCNT12	= 0x04	# 12 alarms in total
	DPV1PRM2_ALRMCNT16	= 0x05	# 16 alarms in total
	DPV1PRM2_ALRMCNT24	= 0x06	# 24 alarms in total
	DPV1PRM2_ALRMCNT32	= 0x07	# 32 alarms in total
	DPV1PRM2_PRMBLK		= 0x08	# Parameter block follows
	DPV1PRM2_ISO		= 0x10	# Isochronous mode
	DPV1PRM2_R5		= 0x20	# Reserved bit 5
	DPV1PRM2_R6		= 0x40	# Reserved bit 6
	DPV1PRM2_REDUN		= 0x80	# Redundancy commands on

	def __init__(self, da, sa,
		     fc=FdlTelegram.FC_SRD_HI |
		        FdlTelegram.FC_REQ,
		     dsap=DpTelegram.DSAP_SET_PRM,
		     ssap=DpTelegram.SSAP_MS0):
		DpTelegram.__init__(self, da=da, sa=sa, fc=fc,
				    dsap=dsap, ssap=ssap)
		self.stationStatus = self.STA_LOCK	# Station_Status
		self.wdFact1 = 1			# WD_Fact_1
		self.wdFact2 = 1			# WD_Fact_2
		self.minTSDR = 0			# min_Tsdr (0 = no change)
		self.identNumber = 0			# Ident_Number
		self.groupIdent = 0			# Group_Ident (Lock_Req must be set)
		self.clearUserPrmData()

	def __repr__(self):
		return "DpTelegram_SetPrm_Req(da=%s, sa=%s, fc=%s, " \
			"dsap=%s, ssap=%s) => " \
			"(stationStatus=%s, wdFact1=%s, wdFact2=%s, " \
			"minTSDR=%s, identNumber=%s, groupIdent=%s " \
			"userPrmData=%s)" %\
			(intToHex(self.da), intToHex(self.sa),
			 intToHex(self.fc),
			 intToHex(self.dsap), intToHex(self.ssap),
			 intToHex(self.stationStatus),
			 intToHex(self.wdFact1), intToHex(self.wdFact2),
			 intToHex(self.minTSDR), intToHex(self.identNumber),
			 intToHex(self.groupIdent),
			 intListToHex(self.userPrmData))

	@classmethod
	def fromFdlTelegram(cls, fdl):
		dp = cls(da=fdl.da,
			 sa=fdl.sa,
			 fc=fdl.fc,
			 dsap=cls.extractSAP(fdl.dae),
			 ssap=cls.extractSAP(fdl.sae))
		try:
			du = fdl.du
			dp.stationStatus = du[0]
			dp.wdFact1 = du[1]
			dp.wdFact2 = du[2]
			dp.minTSDR = du[3]
			dp.identNumber = (du[4] << 8) | du[5]
			dp.groupIdent = du[6]
			dp.userPrmData = du[7:]
		except IndexError:
			raise DpError("Invalid SetPrm telegram format")
		return dp

	def clearUserPrmData(self):
		self.userPrmData = []

	def addUserPrmData(self, data):
		self.userPrmData.extend(data)

	def getDU(self):
		du = [self.stationStatus,
		      self.wdFact1, self.wdFact2,
		      self.minTSDR,
		      (self.identNumber >> 8) & 0xFF,
		      self.identNumber & 0xFF,
		      self.groupIdent]
		du.extend(self.userPrmData)
		return du

class DpCfgDataElement(object):
	# Identifier
	ID_LEN_MASK		= 0x0F	# Length of data
	ID_TYPE_MASK		= 0x30
	ID_TYPE_SPEC		= 0x00	# Specific formats
	ID_TYPE_IN		= 0x10	# Input
	ID_TYPE_OUT		= 0x20	# Output
	ID_TYPE_INOUT		= 0x30	# Input/output
	ID_LEN_WORDS		= 0x40	# Word structure
	ID_CON_WHOLE		= 0x80	# Consistency over whole length

	# Special identifier
	ID_SPEC_MASK		= 0xC0
	ID_SPEC_FREE		= 0x00	# Free place
	ID_SPEC_IN		= 0x40	# 1 byte for input follows
	ID_SPEC_OUT		= 0x80	# 1 byte for output follows
	ID_SPEC_INOUT		= 0xC0	# 1 b for output and 1 b for input follows

	# Length byte
	LEN_COUNT		= 0x3F	# Length of inputs/outputs
	LEN_WORDS		= 0x40	# Word structure
	LEN_CON_WHOLE		= 0x80	# Consistency over whole length

	def __init__(self, identifier=0, lengthBytes=()):
		self.identifier = identifier
		self.lengthBytes = lengthBytes
	
	def __repr__(self):
		return "DpCfgDataElement(identifier=%s, length=%s)" %\
			(intToHex(self.identifier),
			 intListToHex(self.lengthBytes))

	def getDU(self):
		du = [ self.identifier ]
		du.extend(self.lengthBytes)
		return du

class DpTelegram_ChkCfg_Req(DpTelegram):
	def __init__(self, da, sa,
		     fc=FdlTelegram.FC_SRD_HI |
		        FdlTelegram.FC_REQ,
		     dsap=DpTelegram.DSAP_CHK_CFG,
		     ssap=DpTelegram.SSAP_MS0):
		DpTelegram.__init__(self, da=da, sa=sa, fc=fc,
				    dsap=dsap, ssap=ssap)
		self.clearCfgDataElements()

	def __repr__(self):
		return "DpTelegram_ChkCfg_Req(da=%s, sa=%s, fc=%s, " \
			"dsap=%s, ssap=%s) => " \
			"(%s)" %\
			(intToHex(self.da), intToHex(self.sa),
			 intToHex(self.fc),
			 intToHex(self.dsap), intToHex(self.ssap),
			 ", ".join(str(d) for d in self.cfgData))

	def clearCfgDataElements(self):
		self.cfgData = []

	def addCfgDataElement(self, element):
		self.cfgData.append(element)

	@classmethod
	def fromFdlTelegram(cls, fdl):
		dp = cls(da=fdl.da,
			 sa=fdl.sa,
			 fc=fdl.fc,
			 dsap=cls.extractSAP(fdl.dae),
			 ssap=cls.extractSAP(fdl.sae))
		try:
			du = fdl.du
			while du:
				iden = du[0]
				idenType = iden & DpCfgDataElement.ID_TYPE_MASK
				if idenType == DpCfgDataElement.ID_TYPE_SPEC:
					nrBytes = iden & DpCfgDataElement.ID_LEN_MASK
					lengthBytes = du[1:1+nrBytes]
					if len(lengthBytes) != nrBytes:
						raise DpError("Invalid Config identifier")
					cfgData = DpCfgDataElement(identifier=iden,
						lengthBytes=lengthBytes)
					du = du[1+nrBytes:]
				else:
					cfgData = DpCfgDataElement(identifier=iden)
					du = du[1:]
				dp.addCfgDataElement(cfgData)
		except IndexError:
			raise DpError("Invalid Config telegram format")
		return dp

	def getDU(self):
		du = []
		for cfgData in self.cfgData:
			du.extend(cfgData.getDU())
		return du

class _Cfg_Common(DpTelegram):
	def __init__(self, da, sa, fc, dsap, ssap):
		DpTelegram.__init__(self, da=da, sa=sa, fc=fc,
				    dsap=dsap, ssap=ssap)

	def __repr__(self):
		return "_Cfg_Common(da=%s, sa=%s, fc=%s, " \
			"dsap=%s, ssap=%s)" %\
			(intToHex(self.da), intToHex(self.sa),
			 intToHex(self.fc),
			 intToHex(self.dsap), intToHex(self.ssap))

class DpTelegram_GetCfg_Req(_Cfg_Common):
	def __init__(self, da, sa,
		     fc=FdlTelegram.FC_SRD_HI |
		        FdlTelegram.FC_REQ,
		     dsap=DpTelegram.DSAP_GET_CFG,
		     ssap=DpTelegram.SSAP_MS0):
		_Cfg_Common.__init__(self, da=da, sa=sa, fc=fc,
			dsap=dsap, ssap=ssap)

	@classmethod
	def fromFdlTelegram(cls, fdl):
		pass#TODO

class DpTelegram_GetCfg_Con(_Cfg_Common):
	def __init__(self, da, sa,
		     fc=FdlTelegram.FC_DL,
		     dsap=DpTelegram.SSAP_MS0,
		     ssap=DpTelegram.DSAP_GET_CFG):
		_Cfg_Common.__init__(self, da=da, sa=sa,
			fc=fc, dsap=dsap, ssap=ssap)

	@classmethod
	def fromFdlTelegram(cls, fdl):
		pass#TODO

class DpTelegram_GlobalControl(DpTelegram):
	# Control_Command bits
	CCMD_CLEAR		= 0x02	# Clear_Data: Clear all outputs
	CCMD_UNFREEZE		= 0x04	# Unfreeze: Freezing is cancelled
	CCMD_FREEZE		= 0x08	# Freeze: Inputs are frozen
	CCMD_UNSYNC		= 0x10	# Unsync: Syncing is cancelled
	CCMD_SYNC		= 0x20	# Sync: Outputs are synced

	# Group_Select values
	GSEL_BROADCAST		= 0x00	# All slaves are addressed
	GSEL_GROUP1		= 0x01	# Group 1 is addressed
	GSEL_GROUP2		= 0x02	# Group 2 is addressed
	GSEL_GROUP3		= 0x04	# Group 3 is addressed
	GSEL_GROUP4		= 0x08	# Group 4 is addressed
	GSEL_GROUP5		= 0x10	# Group 5 is addressed
	GSEL_GROUP6		= 0x20	# Group 6 is addressed
	GSEL_GROUP7		= 0x40	# Group 7 is addressed
	GSEL_GROUP8		= 0x80	# Group 8 is addressed

	def __init__(self, da, sa,
		     fc=FdlTelegram.FC_SDN_HI |
		        FdlTelegram.FC_REQ,
		     dsap=DpTelegram.DSAP_GLOBAL_CONTROL,
		     ssap=DpTelegram.SSAP_MS0):
		DpTelegram.__init__(self, da=da, sa=sa, fc=fc,
				    dsap=dsap, ssap=ssap)
		self.controlCommand = 0			# Control_Command
		self.groupSelect = self.GSEL_BROADCAST	# Group_Select

	def __repr__(self):
		return "DpTelegram_GlobalControl(da=%s, sa=%s, fc=%s, " \
			"dsap=%s, ssap=%s)" %\
			(intToHex(self.da), intToHex(self.sa),
			 intToHex(self.fc),
			 intToHex(self.dsap), intToHex(self.ssap))

	@classmethod
	def fromFdlTelegram(cls, fdl):
		dp = cls(da=fdl.da,
			 sa=fdl.sa,
			 fc=fdl.fc,
			 dsap=cls.extractSAP(fdl.dae),
			 ssap=cls.extractSAP(fdl.sae))
		try:
			dp.controlCommand = fdl.du[0]
			dp.groupSelect = fdl.du[1]
		except IndexError:
			raise DpError("Invalid Global_Control telegram format")
		return dp

	def getDU(self):
		return [self.controlCommand, self.groupSelect]
