#!/usr/bin/env python3
#
# Simple pyprofibus example
#
# This example initializes an S7-315-2DP configured as slave,
# reads its input data and writes the data back to the module.
#

import sys
import pyprofibus
from pyprofibus import DpTelegram_SetPrm_Req, monotonic_time


master = None
try:
	# Parse the config file.
	config = pyprofibus.PbConf.fromFile("example_s7-315-2dp.conf")

	# Create a PHY (layer 1) interface object
	phy = config.makePhy()

	# Create a DP class 1 master with DP address 1
	master = pyprofibus.DPM1(phy = phy,
				 masterAddr = config.dpMasterAddr,
				 debug = True)

	# Create a slave descriptions.
	for slaveConf in config.slaveConfs:
		gsd = slaveConf.gsd

		# Create a slave description for an S7-315-2DP
		slaveDesc = pyprofibus.DpSlaveDesc(identNumber = gsd.getIdentNumber(),
						   slaveAddr = slaveConf.addr)

		# Create Chk_Cfg telegram
		slaveDesc.setCfgDataElements(gsd.getCfgDataElements())

		# Set User_Prm_Data
		slaveDesc.setUserPrmData(gsd.getUserPrmData())

		# Set various standard parameters
		slaveDesc.setSyncMode(slaveConf.syncMode)
		slaveDesc.setFreezeMode(slaveConf.freezeMode)
		slaveDesc.setGroupMask(slaveConf.groupMask)
		slaveDesc.setWatchdog(slaveConf.watchdogMs)

		# Register the S7-315-2DP slave at the DPM
		master.addSlave(slaveDesc)

	# Initialize the DPM
	master.initialize()
	slaveDescs = master.getSlaveList()

	# Cyclically run Data_Exchange.
	inData = [0]
	rtSum, runtimes, nextPrint = 0, [ 0, ] * 512, monotonic_time() + 1.0
	while True:
		start = monotonic_time()

		# Run slave state machines.
		for slaveDesc in slaveDescs:
			outData = inData
			inDataTmp = master.runSlave(slaveDesc, outData)
			if inDataTmp is not None:
				inData = inDataTmp

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
