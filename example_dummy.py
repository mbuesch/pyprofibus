#!/usr/bin/env python3
#
# Simple pyprofibus dummy example using dummy PHY.
# This example can be run without any PB hardware.
#

import sys
import pyprofibus, pyprofibus.phy_dummy
from pyprofibus import DpTelegram_SetPrm_Req, monotonic_time


master = None
try:
	# Parse the config file.
	config = pyprofibus.PbConf.fromFile("example_dummy.conf")

	# Create a PHY (layer 1) interface object
	phy = config.makePhy()

	# Create a DP class 1 master with DP address 1
	master = pyprofibus.DPM1(phy = phy,
				 masterAddr = config.dpMasterAddr,
				 debug = True)

	# Create a slave descriptions.
	for slaveConf in config.slaveConfs:
		gsd = slaveConf.gsd

		slaveDesc = pyprofibus.DpSlaveDesc(
				identNumber = gsd.getIdentNumber(),
				slaveAddr = slaveConf.addr)

		# Create Chk_Cfg telegram elements
		slaveDesc.setCfgDataElements(gsd.getCfgDataElements())

		# Set User_Prm_Data
		dp1PrmMask = bytearray((DpTelegram_SetPrm_Req.DPV1PRM0_FAILSAFE,
					DpTelegram_SetPrm_Req.DPV1PRM1_REDCFG,
					0x00))
		dp1PrmSet  = bytearray((DpTelegram_SetPrm_Req.DPV1PRM0_FAILSAFE,
					DpTelegram_SetPrm_Req.DPV1PRM1_REDCFG,
					0x00))
		slaveDesc.setUserPrmData(gsd.getUserPrmData(dp1PrmMask = dp1PrmMask,
							    dp1PrmSet = dp1PrmSet))

		# Set various standard parameters
		slaveDesc.setSyncMode(slaveConf.syncMode)
		slaveDesc.setFreezeMode(slaveConf.freezeMode)
		slaveDesc.setGroupMask(slaveConf.groupMask)
		slaveDesc.setWatchdog(slaveConf.watchdogMs)

		# Register the slave at the DPM
		master.addSlave(slaveDesc)

	# Initialize the DPM
	master.initialize()
	slaveDescs = master.getSlaveList()

	# Run the slave state machine.
	slaveData = [ bytearray((0x42, 0x24,)) ] * len(slaveDescs)
	rtSum, runtimes, nextPrint = 0, [ 0, ] * 512, monotonic_time() + 1.0
	while True:
		start = monotonic_time()

		# Run slave state machines.
		for i, slaveDesc in enumerate(slaveDescs):
			inData = master.runSlave(slaveDesc, slaveData[i])
			if inData is not None:
				slaveData[i] = bytearray((inData[1], inData[0]))

		# Print statistics.
		end = monotonic_time()
		runtimes.append(end - start)
		rtSum = rtSum - runtimes.pop(0) + runtimes[-1]
		if end > nextPrint:
			nextPrint = end + 3.0
			sys.stderr.write("pyprofibus cycle time = %.3f ms\n" %\
				(rtSum / len(runtimes) * 1000.0))

except pyprofibus.ProfibusError as e:
	print("Terminating: %s" % str(e))
finally:
	if master:
		master.destroy()
