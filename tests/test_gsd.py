from __future__ import division, absolute_import, print_function, unicode_literals
from pyprofibus_tstlib import *
initTest(__file__)

import pyprofibus
import os


class Test_GSD(TestCase):
	def test_modular(self):
		gsd = pyprofibus.GsdInterp.fromFile(os.path.join("misc", "dummy_modular.gsd"))
		gsd.setConfiguredModule("dummy input module")
		gsd.setConfiguredModule("dummy output module")

		self.assertEqual([ e.getDU()
					for e in gsd.getCfgDataElements() ],
				 [ [0x00, ], [0x10, ], [0x20, ], ])
		self.assertEqual(gsd.getIdentNumber(), 0x4224)
		self.assertEqual(gsd.getUserPrmData(), bytearray([0x00, 0x00, 0x00, 0x42]))

	def test_compact(self):
		gsd = pyprofibus.GsdInterp.fromFile(os.path.join("misc", "dummy_compact.gsd"))
		self.assertEqual([ e.getDU()
					for e in gsd.getCfgDataElements() ],
				 [ [0x00, ], [0x10, ], [0x20, ], ])
		self.assertEqual(gsd.getIdentNumber(), 0x4224)
		self.assertEqual(gsd.getUserPrmData(), bytearray([0x00, 0x00, 0x00, 0x42]))
