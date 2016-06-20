from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus_tstlib import *


def test_gsdinterp():
	gsd = pyprofibus.GsdInterp.fromFile("dummy.gsd")
	gsd.setConfiguredModule("dummy input module")
	gsd.setConfiguredModule("dummy output module")

	assert_eq([ e.getDU()
		    for e in gsd.getCfgDataElements() ],
		  [ [0x00, ], [0x10, ], [0x20, ], ])
	assert_eq(gsd.getIdentNumber(), 0x4224)
	assert_eq(gsd.getUserPrmData(), bytearray([0x00, 0x00, 0x00, 0x42]))
