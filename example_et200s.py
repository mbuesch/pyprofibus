#!/usr/bin/env python3
#
# Simple pyprofibus example
#
# This example initializes an ET-200S slave, reads input
# data and writes the data back to the module.
#
# The hardware configuration is as follows:
#
#   v--------------v----------v----------v----------v----------v
#   |     IM 151-1 | PM-E     | 2 DO     | 2 DO     | 4 DI     |
#   |     STANDARD | DC24V    | DC24V/2A | DC24V/2A | DC24V    |
#   |              |          |          |          |          |
#   |              |          |          |          |          |
#   | ET 200S      |          |          |          |          |
#   |              |          |          |          |          |
#   |              |          |          |          |          |
#   |       6ES7   | 6ES7     | 6ES7     | 6ES7     | 6ES7     |
#   |       151-   | 138-     | 132-     | 132-     | 131-     |
#   |       1AA04- | 4CA01-   | 4BB30-   | 4BB30-   | 4BD01-   |
#   |       0AB0   | 0AA0     | 0AA0     | 0AA0     | 0AA0     |
#   ^--------------^----------^----------^----------^----------^
#

import sys
import pyprofibus
from pyprofibus import DpTelegram_SetPrm_Req, monotonic_time


master = None
try:
	# Parse the config file.
	config = pyprofibus.PbConf.fromFile("example_et200s.conf")

	# Create a PHY (layer 1) interface object
	phy = config.makePhy()

	# Create a DP class 1 master with DP address 1
	master = pyprofibus.DPM1(phy = phy,
				 masterAddr = config.dpMasterAddr,
				 debug = True)

	# Create a slave descriptions.
	for slaveConf in config.slaveConfs:
		gsd = slaveConf.gsd

		# Create a slave description for an ET-200S.
		# The ET-200S has got the DP address 8 set via DIP-switches.
		slaveDesc = pyprofibus.DpSlaveDesc(identNumber = gsd.getIdentNumber(),
						   slaveAddr = slaveConf.addr)

		# Create Chk_Cfg telegram
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

		# Register the ET-200S slave at the DPM
		master.addSlave(slaveDesc)

	# Initialize the DPM
	master.initialize()
	slaveDescs = master.getSlaveList()

	# Cyclically run Data_Exchange.
	# 4 input bits from the 4-DI module are copied to
	# the two 2-DO modules.
	inData = 0
	rtSum, runtimes, nextPrint = 0, [ 0, ] * 512, monotonic_time() + 1.0
	while True:
		start = monotonic_time()

		# Run slave state machines.
		for slaveDesc in slaveDescs:
			outData = [inData & 3, (inData >> 2) & 3]
			inDataTmp = master.runSlave(slaveDesc, outData)
			if inDataTmp is not None:
				inData = inDataTmp[0]

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
