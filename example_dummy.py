#!/usr/bin/env python3
#
# Simple pyprofibus dummy example using dummy PHY.
# This example can be run without any PB hardware.
#

import sys
import pyprofibus
import pyprofibus.phy_dummy
from pyprofibus import ProfibusError, monotonic_time
from pyprofibus.gsd.interp import GsdInterp
from pyprofibus.dp import DpTelegram_SetPrm_Req


master = None
try:
	# Parse the GSD file.
	# And select the plugged modules.
	gsd = GsdInterp.fromFile("dummy.gsd", debug = False)
	gsd.setConfiguredModule("dummy output module")
	gsd.setConfiguredModule("dummy output module")
	gsd.setConfiguredModule("dummy input module")

	# Create a PHY (layer 1) interface object
	phy = pyprofibus.phy_dummy.CpPhyDummySlave(debug = False)
	phy.setConfig(19200)

	# Create a DP class 1 master with DP address 1
	master = pyprofibus.DPM1(phy = phy,
				 masterAddr = 2,
				 debug = True)

	# Create a slave description.
	slaveDesc = pyprofibus.DpSlaveDesc(identNumber = gsd.getIdentNumber(),
					   slaveAddr = 8)

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
	slaveDesc.setSyncMode(True)	# Sync-mode supported
	slaveDesc.setFreezeMode(True)	# Freeze-mode supported
	slaveDesc.setGroupMask(1)	# Group-ident 1
	slaveDesc.setWatchdog(300)	# Watchdog: 300 ms

	# Register the slave at the DPM
	master.addSlave(slaveDesc)

	# Run the slave state machine.
	master.initialize()
	outData = bytearray( (0x42, 0x24,) )
	rtSum, runtimes, nextPrint = 0, [ 0, ] * 512, monotonic_time() + 1.0
	while 1:
		start = monotonic_time()

		inData = master.runSlave(slaveDesc, outData)
		if inData is not None:
			outData = bytearray( (inData[1], inData[0]) )

		end = monotonic_time()
		runtimes.append(end - start)
		rtSum = rtSum - runtimes.pop(0) + runtimes[-1]
		if end > nextPrint:
			nextPrint = end + 3.0
			sys.stderr.write("pyprofibus cycle time = %.3f ms\n" %\
				(rtSum / len(runtimes) * 1000.0))

except ProfibusError as e:
	print("Terminating: %s" % str(e))
finally:
	if master:
		master.destroy()
