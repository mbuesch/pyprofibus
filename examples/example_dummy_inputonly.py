#!/usr/bin/env python3
#
# Simple pyprofibus dummy example using dummy PHY.
# This example can be run without any PB hardware.
#

import sys
sys.path.insert(0, "..")
import pyprofibus
import time

def main(confdir=".", watchdog=None):
	master = None
	try:
		# Parse the config file.
		config = pyprofibus.PbConf.fromFile(confdir + "/example_dummy_inputonly.conf")

		# Create a DP master.
		master = config.makeDPM()

		# Create the slave descriptions.
		outData = {}
		for slaveConf in config.slaveConfs:
			slaveDesc = slaveConf.makeDpSlaveDesc()

			# Set User_Prm_Data
			dp1PrmMask = bytearray((pyprofibus.dp.DpTelegram_SetPrm_Req.DPV1PRM0_FAILSAFE,
						pyprofibus.dp.DpTelegram_SetPrm_Req.DPV1PRM1_REDCFG,
						0x00))
			dp1PrmSet  = bytearray((pyprofibus.dp.DpTelegram_SetPrm_Req.DPV1PRM0_FAILSAFE,
						pyprofibus.dp.DpTelegram_SetPrm_Req.DPV1PRM1_REDCFG,
						0x00))
			slaveDesc.setUserPrmData(slaveConf.gsd.getUserPrmData(dp1PrmMask=dp1PrmMask,
									      dp1PrmSet=dp1PrmSet))


			# Register the slave at the DPM
			master.addSlave(slaveDesc)

			# Set initial output data.
			outData[slaveDesc.name] = bytearray((0x42, 0x24))

		# Initialize the DPM
		master.initialize()

		# Run the slave state machine.
		while True:
			# Write the output data.
			for slaveDesc in master.getSlaveList():
				slaveDesc.setMasterOutData(outData[slaveDesc.name])

			# Run slave state machines.
			handledSlaveDesc = master.run()

			# Get the in-data (receive)
			if handledSlaveDesc:
				inData = handledSlaveDesc.getMasterInData()
				# This slave will not send any data. It's input-only (see config).
				assert inData is None

			# Feed the system watchdog, if it is available.
			if watchdog is not None:
				watchdog()
			# Slow down main loop. Just for debugging.
			time.sleep(0.01)

	except pyprofibus.ProfibusError as e:
		print("Terminating: %s" % str(e))
		return 1
	finally:
		if master:
			master.destroy()
	return 0

if __name__ == "__main__":
	import sys
	sys.exit(main())
