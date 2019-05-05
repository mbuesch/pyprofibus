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

	outData = {}

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

		# Set initial output data.
		outData[slaveDesc.slaveAddr] = bytearray((0x00, ))

	# Initialize the DPM
	master.initialize()

	# Cyclically run Data_Exchange.
	while True:
		# Write the output data.
		for slaveDesc in master.getSlaveList():
			slaveDesc.setOutData(outData[slaveDesc.slaveAddr])

		# Run slave state machines.
		handledSlaveDesc = master.run()

		# Get the in-data (receive) and set it as out-data (transmit).
		if handledSlaveDesc:
			inData = handledSlaveDesc.getInData()
			if inData is not None:
				# In our example the output data shall be a mirror of the input.
				outData[handledSlaveDesc.slaveAddr] = inData

except pyprofibus.ProfibusError as e:
	print("Terminating: %s" % str(e))
finally:
	if master:
		master.destroy()
