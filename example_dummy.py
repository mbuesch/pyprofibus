#!/usr/bin/env python3
#
# Simple pyprofibus dummy example using dummy PHY.
# This example can be run without any PB hardware.
#

import pyprofibus

master = None
try:
	# Parse the config file.
	config = pyprofibus.PbConf.fromFile("example_dummy.conf")

	# Create a DP master.
	master = config.makeDPM()

	# Create the slave descriptions.
	outData = {}
	for slaveConf in config.slaveConfs:
		slaveDesc = slaveConf.makeDpSlaveDesc()

		# Register the slave at the DPM
		master.addSlave(slaveDesc)

		# Set initial output data.
		outData[slaveDesc.slaveAddr] = bytearray((0x42, 0x24))

	# Initialize the DPM
	master.initialize()

	# Run the slave state machine.
	while True:
		# Write the output data.
		for slaveDesc in master.getSlaveList():
			slaveDesc.setOutData(outData[slaveDesc.slaveAddr])

		# Run slave state machines.
		handledSlaveDesc = master.run()

		# Get the in-data (receive)
		if handledSlaveDesc:
			inData = handledSlaveDesc.getInData()
			if inData is not None:
				# In our example the output data shall be the inverted input.
				outData[handledSlaveDesc.slaveAddr][0] = inData[1]
				outData[handledSlaveDesc.slaveAddr][1] = inData[0]

except pyprofibus.ProfibusError as e:
	print("Terminating: %s" % str(e))
finally:
	if master:
		master.destroy()
