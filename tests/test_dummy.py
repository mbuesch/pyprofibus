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

	for i in range(25):
		ret = master.runSlave(slaveDesc, bytearray([1, ]))
	for i in range(2, 100):
		print("testing %d" % i)
		ret = master.runSlave(slaveDesc, bytearray([i, ]))
		assert_eq(bytearray(ret), bytearray([(i - 1) ^ 0xFF, ]))
