class SerialException(Exception):
	pass

class Serial(object):
	def open(self):
		raise NotImplementedError

	def close(self):
		raise NotImplementedError

PARITY_EVEN = "PARITY_EVEN"
STOPBITS_ONE = "STOPBITS_ONE"
