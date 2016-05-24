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

import pyprofibus
import pyprofibus.phy_serial


# The serial port that we connect to
port = "/dev/ttyAMA0"

# Enable verbose debug messages?
debug = True

# Create a PHY (layer 1) interface object
phy = pyprofibus.phy_serial.CpPhySerial(port = port,
					debug = debug)
phy.setConfig(19200)

# Create a DP class 1 master with DP address 1
master = pyprofibus.DPM1(phy = phy,
			 masterAddr = 2,
			 debug = debug)

# Create a slave description for an ET-200S.
# The ET-200S has got the DP address 8 set via DIP-switches.
et200s = pyprofibus.DpSlaveDesc(identNumber = 0x806A,
				slaveAddr = 8)

# Create Chk_Cfg telegram elements
for elem in (pyprofibus.DpCfgDataElement(0),		# PM-E module
	     pyprofibus.DpCfgDataElement(0x20),		# 2-DO module
	     pyprofibus.DpCfgDataElement(0x20),		# 2-DO module
	     pyprofibus.DpCfgDataElement(0x10)):	# 4-DI module
	et200s.chkCfgTelegram.addCfgDataElement(elem)

# Set User_Prm_Data
userPrm = [0x60, 0x00, 0x00, 0x11, 0x21, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x01,
	   0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
	   0x20, 0x01, 0x00, 0x11, 0x11, 0x18]
et200s.setPrmTelegram.addUserPrmData(userPrm)

# Set various standard parameters
et200s.setSyncMode(True)		# Sync-mode supported
et200s.setFreezeMode(True)		# Freeze-mode supported
et200s.setGroupMask(1)			# Group-ident 1
et200s.setWatchdog(300)			# Watchdog: 300 ms

# Register the ET-200S slave at the DPM
master.addSlave(et200s)

try:
	# Initialize the DPM and all registered slaves
	master.initialize()

	# Cyclically run Data_Exchange.
	# 4 input bits from the 4-DI module are copied to
	# the two 2-DO modules.
	inData = 0
	while 1:
		outData = [inData & 3, (inData >> 2) & 3]
		inDataTmp = master.runSlave(et200s, outData)
		if inDataTmp is not None:
			inData = inDataTmp[0]
except:
	print("Terminating.")
	master.destroy()
	raise
