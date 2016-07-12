from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus_tstlib import *


def test_dummy_phy():
	phy = pyprofibus.phy_dummy.CpPhyDummySlave(debug = True)
	phy.setConfig(baudrate = 19200)

	master = pyprofibus.DPM1(phy = phy,
				 masterAddr = 42,
				 debug = True)

	slaveDesc = pyprofibus.DpSlaveDesc(
			identNumber = 0x6666,
			slaveAddr = 84)

	slaveDesc.setCfgDataElements([
		pyprofibus.DpCfgDataElement(pyprofibus.DpCfgDataElement.ID_TYPE_OUT),
		pyprofibus.DpCfgDataElement(pyprofibus.DpCfgDataElement.ID_TYPE_IN),
	])

	slaveDesc.setUserPrmData(bytearray([1, 2, 3, 4, ]))

	slaveDesc.setSyncMode(True)
	slaveDesc.setFreezeMode(True)
	slaveDesc.setGroupMask(1)
	slaveDesc.setWatchdog(300)

	master.addSlave(slaveDesc)
	master.initialize()

	# Run slave initialization state machine.
	for i in range(25):
		ret = master.runSlave(slaveDesc, bytearray([1, ]))
	# Check dummy-slave response to Data_Exchange.
	for i in range(100):
		print("testing %d" % i)
		j = 0
		while True:
			j += 1
			assert_lt(j, 10)
			ret = master.runSlave(slaveDesc, bytearray([i, ]))
			if j >= 5 and ret is not None:
				break
		assert_eq(bytearray(ret), bytearray([i ^ 0xFF, ]))
