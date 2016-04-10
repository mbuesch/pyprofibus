#
# PROFIBUS DP - Communication Processor PHY access library
#
# Copyright (c) 2013-2016 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

import time
import sys

from pyprofibus.util import *


class PhyError(ProfibusError):
	pass

class CpPhy(object):
	# Profibus baud-rates
	PB_PHY_BAUD_9600	= 0
	PB_PHY_BAUD_19200	= 1
	PB_PHY_BAUD_45450	= 2
	PB_PHY_BAUD_93750	= 3
	PB_PHY_BAUD_187500	= 4
	PB_PHY_BAUD_500000	= 5
	PB_PHY_BAUD_1500000	= 6
	PB_PHY_BAUD_3000000	= 7
	PB_PHY_BAUD_6000000	= 8
	PB_PHY_BAUD_12000000	= 9

	baud2id = {
		9600		: PB_PHY_BAUD_9600,
		19200		: PB_PHY_BAUD_19200,
		45450		: PB_PHY_BAUD_45450,
		93750		: PB_PHY_BAUD_93750,
		187500		: PB_PHY_BAUD_187500,
		500000		: PB_PHY_BAUD_500000,
		1500000		: PB_PHY_BAUD_1500000,
		3000000		: PB_PHY_BAUD_3000000,
		6000000		: PB_PHY_BAUD_6000000,
		12000000	: PB_PHY_BAUD_12000000,
	}

	def __init__(self, debug=False):
		pass#TODO

	def cleanup(self):
		pass#TODO

	# Poll for received packet.
	# timeout => In seconds. 0 = none, Negative = unlimited.
	def poll(self, timeout=0):
		pass#TODO

	def sendReset(self):
		pass#TODO

	def profibusSetPhyConfig(self, baudrate=19200,
				 rxTimeoutMs=100,
				 bitErrorChecks=True):
		pass#TODO

	def profibusSend_SDN(self, telegramData):
		pass#TODO

	def profibusSend_SRD(self, telegramData):
		pass#TODO
