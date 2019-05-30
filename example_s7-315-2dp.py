#!/usr/bin/env python3
#
# Simple pyprofibus example
#
# This example initializes an S7-315-2DP configured as slave,
# reads its input data and writes the data back to the module.
#

import pyprofibus

master = None
try:
	# Parse the config file.
	config = pyprofibus.PbConf.fromFile("example_s7-315-2dp.conf")

	# Create a DP master.
	master = config.makeDPM()

	# Create the slave descriptions.
	outData = {}
	for slaveConf in config.slaveConfs:
		slaveDesc = slaveConf.makeDpSlaveDesc()

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
