#
# PROFIBUS - Abstract transceiver
#
# Copyright (c) 2013 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2,
# or (at your option) any later version.
#


class AbstractTransceiver(object):
	def sendSync(self, telegram, timeout):
		self.send(telegram)
		return self.poll(timeout)
