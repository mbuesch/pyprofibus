# -*- coding: utf-8 -*-
#
# Driver for FPGA based PROFIBUS PHY.
#
# Copyright (c) 2019 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#

from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus.compat import *

from pyprofibus.phy import PhyError


__all__ = [
	"FpgaPhyError",
]


class FpgaPhyError(PhyError):
	def __init__(self, msg, *args, **kwargs):
		msg = "PHY-FPGA: " + str(msg)
		super(FpgaPhyError, self).__init__(msg, *args, **kwargs)
