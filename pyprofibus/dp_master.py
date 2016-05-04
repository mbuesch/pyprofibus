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

	_STATE_INVALID	= -1
	STATE_INIT	= 0 # Initialize
	STATE_WDIAG	= 1 # Wait for diagnosis
	STATE_WPRM	= 2 # Wait for Prm telegram
	STATE_WCFG	= 3 # Wait for Cfg telegram
	STATE_WDXRDY	= 4 # Wait for Data_Exchange ready
	STATE_DX	= 5 # Data_Exchange

	state2name = {
		_STATE_INVALID	: "invalid",
		STATE_INIT	: "init",
		STATE_WDIAG	: "wait for diag",
		STATE_WPRM	: "wait for Prm",
		STATE_WCFG	: "wait for Cfg",
		STATE_WDXRDY	: "wait for Data_Exchange ready",
		STATE_DX	: "Data_Exchange",
	}

	def __init__(self, slaveDesc):
		self.slaveDesc = slaveDesc

		self.__state = self._STATE_INVALID
		self.__nextState = self._STATE_INVALID
		self.__prevState = self._STATE_INVALID
		self.setState(self.STATE_INIT)
		self.applyState()

		# Context for FC-Bit toggeling
		self.fcb = FdlFCB()

		# Currently running request telegram
		self.req = None

		self.faultDeb = FaultDebouncer()
		self.limit = TimeLimited(0.01)	# timeout object

	def getState(self):
		return self.__state

	def getNextState(self):
		return self.__nextState

	def setState(self, state):
		self.__nextState = state

	def applyState(self):
		self.__prevState, self.__state = self.__state, self.__nextState

	def stateChanged(self):
		return self.__prevState != self.__state

	def stateIsChanging(self):
		return self.__nextState != self.__state

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

	def setSyncMode(self, enabled):
		"""Enable/disable sync-mode.
		Must be called before parameterisation."""

		if enabled:
			self.setPrmTelegram.stationStatus |= DpTelegram_SetPrm_Req.STA_SYNC
		else:
			self.setPrmTelegram.stationStatus &= ~DpTelegram_SetPrm_Req.STA_SYNC

	def setFreezeMode(self, enabled):
		"""Enable/disable freeze-mode.
		Must be called before parameterisation."""

		if enabled:
			self.setPrmTelegram.stationStatus |= DpTelegram_SetPrm_Req.STA_FREEZE
		else:
			self.setPrmTelegram.stationStatus &= ~DpTelegram_SetPrm_Req.STA_FREEZE

	def setGroupMask(self, groupMask):
		"""Assign the slave to one or more groups.
		Must be called before parameterisation."""

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

		mcastSlaveDesc = DpSlaveDesc(
			identNumber = 0,
			slaveAddr = FdlTelegram.ADDRESS_MCAST)
		mcastSlave = DpSlaveState(mcastSlaveDesc)

		self.__slaveDescs = {
			FdlTelegram.ADDRESS_MCAST : mcastSlaveDesc,
		}
		self.__slaveStates = {
			FdlTelegram.ADDRESS_MCAST : mcastSlave,
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
		self.__slaveStates[slaveAddr] = DpSlaveState(slaveDesc)

	def getSlaveList(self):
		"""Get a list of registered DpSlaveDescs, sorted by address."""

		return [ desc for addr, desc in sorted(self.__slaveDescs.items(),
						       key = lambda x: x[0])
			 if addr != FdlTelegram.ADDRESS_MCAST ]

	def __runSlave_init(self, slave, dataExOutData):
		da, sa = slave.slaveDesc.slaveAddr, self.masterAddr

		if slave.stateChanged():
			self.__debugMsg("Trying to initialize slave %d..." % da)

			# Disable the FCB bit.
			slave.fcb.enableFCB(False)

			slave.req = FdlTelegram_FdlStat_Req(da=da, sa=sa)

		try:
			ok, reply = self.fdlTrans.sendSync(
				fcb=slave.fcb, telegram=slave.req, timeout=0.1)
		except ProfibusError as e:
			ok, reply = False, None
			self.__debugMsg("FdlStat_Req failed: %s" % str(e))
		if ok and reply and reply.fc is not None:
			stype = reply.fc & FdlTelegram.FC_STYPE_MASK
			if reply.fc & FdlTelegram.FC_REQ:
				self.__debugMsg("Slave %d replied with "
						"request bit set." % da)
			elif stype != FdlTelegram.FC_SLAVE:
				self.__debugMsg("Device %d is not a slave. "
						"Detected type: 0x%02X" % (
						da, stype))
			else:
				slave.setState(slave.STATE_WDIAG)
		return None

	def __runSlave_waitDiag(self, slave, dataExOutData):
		da, sa = slave.slaveDesc.slaveAddr, self.masterAddr

		if slave.stateChanged():
			# Enable the FCB bit.
			slave.fcb.enableFCB(True)

			# Send a SlaveDiag request
			self.__debugMsg("Requesting Slave_Diag from slave %d..." % da)
			slave.req = DpTelegram_SlaveDiag_Req(da=da, sa=sa)

		try:
			ok, reply = self.dpTrans.sendSync(
				fcb=slave.fcb, telegram=slave.req, timeout=0.1)
		except ProfibusError as e:
			ok, reply = False, None
			self.__debugMsg("SlaveDiag_Req failed: %s" % str(e))
		if ok and DpTelegram_SlaveDiag_Con.checkType(reply):
			slave.setState(slave.STATE_WPRM)
		else:
			slave.setState(slave.STATE_INIT)
		return None

	def __runSlave_waitPrm(self, slave, dataExOutData):
		da, sa = slave.slaveDesc.slaveAddr, self.masterAddr

		if slave.stateChanged():
			self.__debugMsg("Sending Set_Prm to slave %d..." % da)
			slave.req = slave.slaveDesc.setPrmTelegram
			slave.req.sa = sa # Assign master address

		try:
			ok, reply = self.dpTrans.sendSync(
				fcb=slave.fcb, telegram=slave.req, timeout=0.3)
		except ProfibusError as e:
			ok, reply = False, None
			self.__debugMsg("Set_Prm failed: %s" % str(e))
		if ok:
			slave.setState(slave.STATE_WCFG)
		else:
			slave.setState(slave.STATE_INIT)
		return None

	def __runSlave_waitCfg(self, slave, dataExOutData):
		da, sa = slave.slaveDesc.slaveAddr, self.masterAddr

		if slave.stateChanged():
			self.__debugMsg("Sending Ckh_Cfg to slave %d..." % da)
			slave.req = slave.slaveDesc.chkCfgTelegram
			slave.req.sa = sa # Assign master address

		try:
			ok, reply = self.dpTrans.sendSync(
				fcb=slave.fcb, telegram=slave.req, timeout=0.3)
		except ProfibusError as e:
			ok, reply = False, None
			self.__debugMsg("Chk_Cfg failed: %s" % str(e))
		if ok:
			slave.setState(slave.STATE_WDXRDY)
		else:
			slave.setState(slave.STATE_INIT)
		return None

	def __runSlave_waitDxRdy(self, slave, dataExOutData):
		da, sa = slave.slaveDesc.slaveAddr, self.masterAddr

		if slave.stateChanged():
			self.__debugMsg("Requesting Slave_Diag from slave %d..." % da)
			slave.limit = TimeLimited(1.0)
			slave.req = DpTelegram_SlaveDiag_Req(da=da, sa=sa)

		try:
			ok, reply = self.dpTrans.sendSync(
				fcb=slave.fcb, telegram=slave.req, timeout=0.1)
		except ProfibusError as e:
			ok, reply = False, None
			self.__debugMsg("SlaveDiag_Req failed: %s" % str(e))
		if ok and DpTelegram_SlaveDiag_Con.checkType(reply):
			if reply.hasExtDiag():
				pass#TODO turn on red DIAG-LED
			if reply.isReadyDataEx():
				slave.setState(slave.STATE_DX)
			elif reply.needsNewPrmCfg() or\
			     slave.limit.exceed():
				slave.setState(slave.STATE_INIT)
		return None

	def __runSlave_dataExchange(self, slave, dataExOutData):
		da, sa = slave.slaveDesc.slaveAddr, self.masterAddr
		dataExInData = None

		if slave.stateChanged():
			self.__debugMsg("Initialization finished. "
				"Running Data_Exchange with slave %d..." % da)
			slave.faultDeb.reset()
		#TODO: add support for in/out- only slaves
		try:
			dataExInData = self.__dataExchange(da, dataExOutData)
			faultCount = slave.faultDeb.faultless()
		except ProfibusError as e:
			self.__debugMsg("Data_Exchange error at "
				"slave %d:\n%s" % (da, str(e)))
			dataExInData = None
			faultCount = slave.faultDeb.fault()
		if faultCount >= 5:
			slave.setState(slave.STATE_INIT)	# communication lost
		elif faultCount >= 3:
			try:
				ready, reply = self.diagSlave(slave.slaveDesc)
				if not ready and reply.needsNewPrmCfg():
					slave.setState(slave.STATE_INIT)
			except ProfibusError as e:
				self.__debugMsg("Diag exception at "
					"slave %d:\n%s" % (da, str(e)))
		return dataExInData

	__slaveStateHandlers = {
		DpSlaveState.STATE_INIT		: __runSlave_init,
		DpSlaveState.STATE_WDIAG	: __runSlave_waitDiag,
		DpSlaveState.STATE_WPRM		: __runSlave_waitPrm,
		DpSlaveState.STATE_WCFG		: __runSlave_waitCfg,
		DpSlaveState.STATE_WDXRDY	: __runSlave_waitDxRdy,
		DpSlaveState.STATE_DX		: __runSlave_dataExchange,
	}

	def runSlave(self, slaveDesc, dataExOutData = None):
		slave = self.__slaveStates[slaveDesc.slaveAddr]

		handler = self.__slaveStateHandlers[slave.getState()]
		dataExInData = handler(self, slave, dataExOutData)

		if slave.stateIsChanging():
			self.__debugMsg("slave[%02X].state --> %s" % (
				slave.slaveDesc.slaveAddr,
				slave.state2name[slave.getNextState()]))
		slave.applyState()

		return dataExInData

	def diagSlave(self, slaveDesc):
		da, sa = slaveDesc.slaveAddr, self.masterAddr
		slave = self.__slaveStates[da]

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
		slave = self.__slaveStates[FdlTelegram.ADDRESS_MCAST]
		globCtl = DpTelegram_GlobalControl(da=FdlTelegram.ADDRESS_MCAST,
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
