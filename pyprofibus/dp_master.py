#
# PROFIBUS DP - Master
#
# Copyright (c) 2013-2016 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from pyprofibus.fdl import *
from pyprofibus.dp import *
from pyprofibus.util import *

import math


#TODO GSD parser

class DpSlaveState():
	"""Run time state of a DP slave that is managed by a DPM instance.
	"""

	def __init__(self):
		self.__state = ""
		self.__nextState = ""
		self.__prevState = ""
		self.setStateInit()
		self.applyState()

		# Context for FC-Bit toggeling
		self.fcb = FdlFCB()

		# Currently running request telegram
		self.req = None

		self.limit = TimeLimited(0.01)	# timeout object
		self.retryCountReset()

	def retryCountReset(self):
		self.__retryCnt = 0

	def retryCountInc(self):
		self.__retryCnt += 1

	def getRetryCount(self):
		return self.__retryCnt

	def setStateInit(self):
		self.__nextState = "init"

	def setStateWaitDiag(self):
		self.__nextState = "wdiag"

	def setStateWaitPrm(self):
		self.__nextState = "wprm"

	def setStateWaitCfg(self):
		self.__nextState = "wcfg"

	def setWaitDxReady(self):
		self.__nextState = "wdxrd"

	def setStateDataEx(self):
		self.__nextState = "dxchg"

	def applyState(self):
		self.__prevState, self.__state = self.__state, self.__nextState

	def stateChanged(self):
		return self.__prevState != self.__state

	def stateIsChanging(self):
		return self.__nextState != self.__state

	def stateIsInit(self):
		return self.__state == "init"

	def stateIsWaitDiag(self):
		return self.__state == "wdiag"

	def stateIsWaitPrm(self):
		return self.__state == "wprm"

	def stateIsWaitCfg(self):
		return self.__state == "wcfg"

	def stateIsWaitDxReady(self):
		return self.__state == "wdxrd"

	def stateIsDataEx(self):
		return self.__state == "dxchg"

	def getCurrentStateName(self):
		return self.__state

	def getNextStateName(self):
		return self.__nextState

class DpSlaveDesc(object):
	"""Static descriptor data of a DP slave that
	is managed by a DPM instance.
	"""

	def __init__(self,
		     identNumber,
		     slaveAddr,
		     inputAddressRangeSize = 0,
		     outputAddressRangeSize = 0):
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

#FIXME not here
		self.isParameterised = False

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

	def __repr__(self):
		return "DPSlaveDesc(identNumber=%s, slaveAddr=%d)" %\
			(intToHex(self.identNumber), self.slaveAddr)

class DpMaster(object):
	def __init__(self, dpmClass, phy, masterAddr, debug=False):
		self.dpmClass = dpmClass
		self.phy = phy
		self.masterAddr = masterAddr
		self.debug = debug

		self.__slaveDescs = {
			FdlTelegram.ADDRESS_MCAST : DpSlaveDesc(
					identNumber = 0,
					slaveAddr = FdlTelegram.ADDRESS_MCAST),
		}
		self.__slaveStates = {
			FdlTelegram.ADDRESS_MCAST : DpSlaveState(),
		}

		# Create the transceivers
		self.fdlTrans = FdlTransceiver(self.phy)
		self.dpTrans = DpTransceiver(self.fdlTrans)

	def __debugMsg(self, msg):
		if self.debug:
			print("DPM%d: %s" % (self.dpmClass, msg))

	def destroy(self):
		#TODO
		if self.phy:
			self.phy.close()
			self.phy = None

	def addSlave(self, slaveDesc):
		"""Register a slave."""

		slaveAddr = slaveDesc.slaveAddr
		if slaveAddr in self.__slaveDescs or\
		   slaveAddr in self.__slaveStates:
			raise DpError("Slave %d is already registered." % slaveAddr)
		self.__slaveDescs[slaveAddr] = slaveDesc
		self.__slaveStates[slaveAddr] = DpSlaveState()

	def getSlaveList(self):
		"""Get a list of registered DpSlaveDescs, sorted by address."""

		return [ desc for addr, desc in sorted(self.__slaveDescs.items(),
						       key = lambda x: x[0])
			 if addr != FdlTelegram.ADDRESS_MCAST ]

	def runSlave(self, slaveDesc, dataExOutData = None):
		da, sa = slaveDesc.slaveAddr, self.masterAddr
		slave = self.__slaveStates[da]
		dataExInData = None

		if slave.stateIsInit():
			if slave.stateChanged():
				slaveDesc.isParameterised = False
				self.__debugMsg("Trying to initialize slave %d..." % da)

				# Disable the FCB bit.
				slave.fcb.enableFCB(False)

				slave.req = FdlTelegram_FdlStat_Req(da=da, sa=sa)

			ok, reply = self.fdlTrans.sendSync(
				fcb=slave.fcb, telegram=slave.req, timeout=0.1)
			if ok and reply:
				stype = reply.fc & FdlTelegram.FC_STYPE_MASK
				if reply.fc & FdlTelegram.FC_REQ:
					self.__debugMsg("Slave %d replied with "
							"request bit set." % da)
				elif stype != FdlTelegram.FC_SLAVE:
					self.__debugMsg("Device %d is not a slave. "
							"Detected type: 0x%02X" % (
							da, stype))
				else:
					slave.setStateWaitDiag()

		elif slave.stateIsWaitDiag():
			if slave.stateChanged():
				# Enable the FCB bit.
				slave.fcb.enableFCB(True)

				# Send a SlaveDiag request
				self.__debugMsg("Requesting Slave_Diag from slave %d..." % da)
				slave.req = DpTelegram_SlaveDiag_Req(da=da, sa=sa)
			ok, reply = self.dpTrans.sendSync(
				fcb=slave.fcb, telegram=slave.req, timeout=0.1)
			if ok and DpTelegram_SlaveDiag_Con.checkType(reply):
				slave.setStateWaitPrm()
			else:
				slave.setStateInit()

		elif slave.stateIsWaitPrm():
			if slave.stateChanged():
				self.__debugMsg("Sending Set_Prm to slave %d..." % da)
				slave.req = slaveDesc.setPrmTelegram
				slave.req.sa = sa # Assign master address
			ok, reply = self.dpTrans.sendSync(
				fcb=slave.fcb, telegram=slave.req, timeout=0.3)
			if ok:
				slave.setStateWaitCfg()
			else:
				slave.setStateInit()

		elif slave.stateIsWaitCfg():
			if slave.stateChanged():
				self.__debugMsg("Sending Ckh_Cfg to slave %d..." % da)
				slave.req = slaveDesc.chkCfgTelegram
				slave.req.sa = sa # Assign master address
			ok, reply = self.dpTrans.sendSync(
				fcb=slave.fcb, telegram=slave.req, timeout=0.3)
			if ok:
				slave.setWaitDxReady()
			else:
				slave.setStateInit()

		elif slave.stateIsWaitDxReady():
			if slave.stateChanged():
				self.__debugMsg("Requesting Slave_Diag from slave %d..." % da)
				slave.limit = TimeLimited(1.0)
				slave.req = DpTelegram_SlaveDiag_Req(da=da, sa=sa)
			ok, reply = self.dpTrans.sendSync(
				fcb=slave.fcb, telegram=slave.req, timeout=0.1)
			if ok and DpTelegram_SlaveDiag_Con.checkType(reply):
				if reply.hasExtDiag():
					pass#TODO turn on red DIAG-LED
				if reply.isReadyDataEx():
					slave.setStateDataEx()
				elif reply.needsNewPrmCfg() or\
				     slave.limit.exceed():
					slave.setStateInit()

		elif slave.stateIsDataEx():
			if slave.stateChanged():
				self.__debugMsg("Initialization finished. "
					"Running Data_Exchange with slave %d..." % da)
				slave.retryCountReset()
				slaveDesc.isParameterised = True
			#TODO: add support for in/out- only slaves
			try:
				dataExInData = self.__dataExchange(da, dataExOutData)
				slave.retryCountReset()
			except ProfibusError as e:
				self.__debugMsg("Data_Exchange error at "
					"slave %d:\n%s" % (da, str(e)))
				dataExInData = None
				slave.retryCountInc()
			retryCount = slave.getRetryCount()
			if retryCount >= 5:
				slave.setStateInit()	# communication lost
			elif retryCount >= 3:
				try:
					ready, reply = self.diagSlave(slaveDesc)
					if not ready and reply.needsNewPrmCfg():
						slave.setStateInit()
				except ProfibusError as e:
					self.__debugMsg("Diag exception at "
						"slave %d:\n%s" % (da, str(e)))

		else:
			assert(0)

		if slave.stateIsChanging():
			self.__debugMsg("slave[%02X].state --> %s" % (
				da, slave.getNextStateName()))
		slave.applyState()

		return dataExInData

	def diagSlave(self, slaveDesc):
		da, sa = slaveDesc.slaveAddr, self.masterAddr

		# Send the final SlaveDiag request to check
		# readyness for data exchange
		self.__debugMsg("Requesting Slave_Diag from "
				"slave %d..." % da)
		req = DpTelegram_SlaveDiag_Req(da=da, sa=sa)
		limit = TimeLimited(1.0)
		ready = False
		while not limit.exceed():
			ok, reply = self.dpTrans.sendSync(
				fcb=slave.fcb, telegram=req, timeout=0.1)
			if ok and DpTelegram_SlaveDiag_Con.checkType(reply):
				if reply.hasExtDiag():
					self.__debugMsg("Slave(%d) hasExtDiag" % da)
				if reply.isReadyDataEx():
					ready = True
					break
				elif reply.needsNewPrmCfg():
					self.__debugMsg("Slave(%d) needsNewPrmCfg" % da)
		else:
			raise DpError("Timeout in SlaveDiag request "
				      "to slave %d" % da)
		return ready, reply

	def diagSlaves(self):
		ready = []
		for slaveDesc in self.getSlaveList():
			ready.append(self.diagSlave(slaveDesc)[0])
		return all(ready)

	def initialize(self):
		"""Initialize the DPM."""

		# Initialize the RX filter
		self.fdlTrans.setRXFilter([self.masterAddr,
					   FdlTelegram.ADDRESS_MCAST])

	def __dataExchange(self, da, outData):
		"""Perform a data exchange with the slave at "da"."""
		try:
			slaveDesc = self.__slaveDescs[da]
			slave = self.__slaveStates[da]
		except KeyError:
			raise DpError("Data_Exchange: da=%d not "
				"found in slave list." % da)
		req = DpTelegram_DataExchange_Req(da=da, sa=self.masterAddr,
						  du=outData)
		ok, reply = self.dpTrans.sendSync(
				fcb=slave.fcb, telegram=req, timeout=0.1)
		if ok and reply:
			if not DpTelegram_DataExchange_Con.checkType(reply):
				raise DpError("Data_Exchange.req reply is not of "
					"Data_Exchange.con type")
			resFunc = reply.fc & FdlTelegram.FC_RESFUNC_MASK
			if resFunc == FdlTelegram.FC_DH or\
			   resFunc == FdlTelegram.FC_RDH:
				pass#TODO: Slave_Diag
			elif resFunc == FdlTelegram.FC_RS:
				raise DpError("Service not active on slave %d" % da)
			return reply.getDU()
		return None

	def __syncFreezeHelper(self, groupMask, controlCommand):
		slaveDesc = self.__slaveDescs[FdlTelegram.ADDRESS_MCAST]
		slave = self.__slaveStates[FdlTelegram.ADDRESS_MCAST]
		globCtl = DpTelegram_GlobalControl(da=slaveDesc.slaveAddr,
						   sa=self.masterAddr)
		globCtl.controlCommand |= controlCommand
		globCtl.groupSelect = groupMask & 0xFF
		ok, reply = self.dpTrans.sendSync(
			fcb=slave.fcb, telegram=globCtl, timeout=0.1)
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
