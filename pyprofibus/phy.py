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
	"""PROFIBUS CP PHYsical layer base class.
	"""

	# Profibus baud-rates
	BAUD_9600	= 9600
	BAUD_19200	= 19200
	BAUD_45450	= 45450
	BAUD_93750	= 93750
	BAUD_187500	= 187500
	BAUD_500000	= 500000
	BAUD_1500000	= 1500000
	BAUD_3000000	= 3000000
	BAUD_6000000	= 6000000
	BAUD_12000000	= 12000000

	def __init__(self, debug = False):
		self.debug = debug

	def close(self):
		pass

	# Poll for received packet.
	# timeout => In seconds. 0 = none, Negative = unlimited.
	def poll(self, timeout = 0):
		raise NotImplementedError

	def setConfig(self, baudrate = BAUD_19200):
		raise NotImplementedError

	def profibusSend_SDN(self, telegramData):
		raise NotImplementedError

	def profibusSend_SRD(self, telegramData):
		raise NotImplementedError
