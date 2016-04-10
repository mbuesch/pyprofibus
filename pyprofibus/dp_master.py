#
# PROFIBUS DP - Master
#
# Copyright (c) 2013 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from pyprofibus.fdl import *
from pyprofibus.dp import *
from pyprofibus.util import *

import math


#TODO GSD parser

class DpSlaveDesc(object):
	def __init__(self,
		     identNumber,
		     slaveAddr,
		     inputAddressRangeSize,
		     outputAddressRangeSize):
		self.identNumber = identNumber
		self.slaveAddr = slaveAddr
		self.inputAddressRangeSize = inputAddressRangeSize
		self.outputAddressRangeSize = outputAddressRangeSize

		# Prepare a Set_Prm telegram.
		self.setPrmTelegram = DpTelegram_SetPrm_Req(
					da = self.slaveAddr,
					sa = None)
		self.setPrmTelegram.identNumber = self.identNumber

		# Prepare a Chk_Cfg telegram.
		self.chkCfgTelegram = DpTelegram_ChkCfg_Req(
					da = self.slaveAddr,
					sa = None)

		self.isParameterised = False

	def __repr__(self):
		return "DPSlaveDesc(identNumber=%s, slaveAddr=%d)" %\
			(intToHex(self.identNumber), self.slaveAddr)

	def setSyncMode(self, enabled):
		"""Enable/disable sync-mode.
		Must be called before parameterisation."""

		assert(not self.isParameterised)
		if enabled:
			self.setPrmTelegram.stationStatus |= DpTelegram_SetPrm_Req.STA_SYNC
		else:
			self.setPrmTelegram.stationStatus &= ~DpTelegram_SetPrm_Req.STA_SYNC

	def setFreezeMode(self, enabled):
		"""Enable/disable freeze-mode.
		Must be called before parameterisation."""

		assert(not self.isParameterised)
		if enabled:
			self.setPrmTelegram.stationStatus |= DpTelegram_SetPrm_Req.STA_FREEZE
		else:
			self.setPrmTelegram.stationStatus &= ~DpTelegram_SetPrm_Req.STA_FREEZE

	def setGroupMask(self, groupMask):
		"""Assign the slave to one or more groups.
		Must be called before parameterisation."""

		assert(not self.isParameterised)
		self.setPrmTelegram.groupIdent = groupMask

	def setWatchdog(self, timeoutMS):
		"""Set the watchdog timeout (in milliseconds).
		If timeoutMS is 0, the watchdog is disabled."""

		if timeoutMS <= 0:
			# Disable watchdog
			self.setPrmTelegram.stationStatus &= ~DpTelegram_SetPrm_Req.STA_WD
			return

		# Enable watchdog
		self.setPrmTelegram.stationStatus |= DpTelegram_SetPrm_Req.STA_WD

		# Set timeout factors
		fact1 = timeoutMS / 10
		fact2 = 1
		while fact1 > 255:
			fact2 *= 2
			fact1 /= 2
			if fact2 > 255:
				raise DpError("Watchdog timeout %d is too big" % timeoutMS)
		fact1 = min(255, int(math.ceil(fact1)))
		self.setPrmTelegram.wdFact1 = fact1
		self.setPrmTelegram.wdFact2 = fact2

class DpMaster(object):
	def __init__(self, dpmClass, phy, masterAddr, debug=False):
		self.dpmClass = dpmClass
		self.phy = phy
		self.masterAddr = masterAddr
		self.debug = debug

		self.slaveDescs = {}

		# Create the transceivers
		self.fdlTrans = FdlTransceiver(self.phy)
		self.dpTrans = DpTransceiver(self.fdlTrans)

	def __debugMsg(self, msg):
		if self.debug:
			print(msg)

	def destroy(self):
		#TODO
		if self.phy:
			self.phy.cleanup()
			self.phy = None

	def addSlave(self, slaveDesc):
		"""Register a slave."""

		self.slaveDescs[slaveDesc.slaveAddr] = slaveDesc

	def getSlaveList(self):
		"""Get a list of registered DpSlaveDescs, sorted by address."""

		return [ desc for addr, desc in sorted(self.slaveDescs.items(),
						       key = lambda x: x[0]) ]

	def __initializeSlave(self, slaveDesc):
		da, sa = slaveDesc.slaveAddr, self.masterAddr

		self.__debugMsg("Initializing slave %d..." % da)

		# Try to request the FDL status
		try:
			req = FdlTelegram_FdlStat_Req(da=da, sa=sa)
			limit = TimeLimited(5.0)
			while not limit.exceed():
				ok, reply = self.fdlTrans.sendSync(telegram=req,
								   timeout=0.1)
				if ok and reply:
					if reply.fc & FdlTelegram.FC_REQ:
						raise DpError("Slave %d replied with "
							"request bit set" % da)
					stype = reply.fc & FdlTelegram.FC_STYPE_MASK
					if stype != FdlTelegram.FC_SLAVE:
						raise DpError("Device %d is not a slave. "
							"Detected type: 0x%02X" %\
							(da, stype))
					break
				limit.sleep(0.1)
			else:
				raise DpError("Timeout in early FDL status request "
					"to slave %d" % da)
		except FdlError as e:
			raise DpError("FDL error in early FDL status request "
				"to slave %d: %s" % (da, str(e)))
		time.sleep(0.1)

		# Enable the FCB bit.
		self.fdlTrans.enableFCB(True)

		# Send a SlaveDiag request
		self.__debugMsg("Requesting Slave_Diag from slave %d..." % da)
		req = DpTelegram_SlaveDiag_Req(da=da, sa=sa)
		limit = TimeLimited(5.0)
		while not limit.exceed():
			ok, reply = self.dpTrans.sendSync(telegram=req,
							  timeout=0.1)
			if ok and reply:
				#TODO checks?
				break
		else:
			raise DpError("Timeout in early SlaveDiag request "
				"to slave %d" % da)
		time.sleep(0.1)

		# Send a SetPrm request
		self.__debugMsg("Sending Set_Prm to slave %d..." % da)
		req = slaveDesc.setPrmTelegram
		req.sa = sa # Assign master address
		ok, reply = self.dpTrans.sendSync(telegram=req,
						  timeout=0.3)
		if not ok:
			raise DpError("SetPrm request to slave %d failed" % da)
		time.sleep(0.2)

		# Send a ChkCfg request
		self.__debugMsg("Sending Ckh_Cfg to slave %d..." % da)
		req = slaveDesc.chkCfgTelegram
		req.sa = sa # Assign master address
		ok, reply = self.dpTrans.sendSync(telegram=req, timeout=0.3)
		if not ok:
			raise DpError("ChkCfg request to slave %d failed" % da)
		time.sleep(0.2)

		# Send the final SlaveDiag request
		self.__debugMsg("Requesting Slave_Diag from slave %d..." % da)
		req = DpTelegram_SlaveDiag_Req(da=da, sa=sa)
		limit = TimeLimited(1.0)
		while not limit.exceed():
			ok, reply = self.dpTrans.sendSync(telegram=req,
							  timeout=0.1)
			if ok and reply:
				#TODO additional checks?
				break
		else:
			raise DpError("Timeout in final SlaveDiag request "
				"to slave %d" % da)
		time.sleep(0.2)

		slaveDesc.isParameterised = True

	def __initializeSlaves(self):
		slaveAddrs = self.slaveDescs.keys()
		for slaveAddr in sorted(slaveAddrs):
			self.__initializeSlave(self.slaveDescs[slaveAddr])

	def initialize(self):
		"""Initialize the DPM."""

		# Initialize the RX filter
		self.fdlTrans.setRXFilter([self.masterAddr,
					   FdlTelegram.ADDRESS_MCAST])

		# Initialize the registered slaves
		self.__initializeSlaves()

	def dataExchange(self, da, outData):
		"""Perform a data exchange with the slave at "da"."""

		req = DpTelegram_DataExchange_Req(da=da, sa=self.masterAddr,
						  du=outData)
		ok, reply = self.dpTrans.sendSync(telegram=req, timeout=0.1)
		if ok and reply:
			if not DpTelegram_DataExchange_Con.checkType(reply):
				raise DpError("Data_Exchange.req reply is not of "
					"Data_Exchange.con type")
			resFunc = reply.fc & FdlTelegram.FC_RESFUNC_MASK
			if resFunc == FdlTelegram.FC_DH or\
			   resFunc == FdlTelegram.FC_RDH:
				pass#TODO: Slave_Diag
			return reply.getDU()
		return None

	def __syncFreezeHelper(self, groupMask, controlCommand):
		globCtl = DpTelegram_GlobalControl(da=FdlTelegram.ADDRESS_MCAST,
						   sa=self.masterAddr)
		globCtl.controlCommand |= controlCommand
		globCtl.groupSelect = groupMask & 0xFF
		ok, reply = self.dpTrans.sendSync(telegram=globCtl, timeout=0.1)
		if ok:
			assert(not reply) # SDN
		else:
			raise DpError("Failed to send Global_Control to "
				"group-mask 0x%02X" % groupMask)

	def syncMode(self, groupMask):
		"""Set SYNC-mode on the specified groupMask.
		If groupMask is 0, all slaves are addressed."""

		self.__syncFreezeHelper(groupMask, DpTelegram_GlobalControl.CCMD_SYNC)

	def syncModeCancel(self, groupMask):
		"""Cancel SYNC-mode on the specified groupMask.
		If groupMask is 0, all slaves are addressed."""

		self.__syncFreezeHelper(groupMask, DpTelegram_GlobalControl.CCMD_UNSYNC)

	def freezeMode(self, groupMask):
		"""Set FREEZE-mode on the specified groupMask.
		If groupMask is 0, all slaves are addressed."""

		self.__syncFreezeHelper(groupMask, DpTelegram_GlobalControl.CCMD_FREEZE)

	def freezeModeCancel(self, groupMask):
		"""Cancel FREEZE-mode on the specified groupMask.
		If groupMask is 0, all slaves are addressed."""

		self.__syncFreezeHelper(groupMask, DpTelegram_GlobalControl.CCMD_UNFREEZE)

class DPM1(DpMaster):
	def __init__(self, phy, masterAddr, debug=False):
		DpMaster.__init__(self, dpmClass=1, phy=phy,
			masterAddr=masterAddr,
			debug=debug)

class DPM2(DpMaster):
	def __init__(self, phy, masterAddr, debug=False):
		DpMaster.__init__(self, dpmClass=2, phy=phy,
			masterAddr=masterAddr,
			debug=debug)
