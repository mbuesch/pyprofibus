from pyprofibus.compat import *

PARITY_EVEN	= "E"
PARITY_ODD	= "O"
STOPBITS_ONE	= 1
STOPBITS_TWO	= 2

class SerialException(Exception):
	pass

class Serial(object):
	def __init__(self):
		self.__isMicropython = isMicropython
		self.port = "/dev/ttyS0"
		self.baudrate = 9600
		self.bytesize = 8
		self.parity = PARITY_EVEN
		self.stopbits = STOPBITS_ONE
		self.timeout = 0
		self.xonxoff = False
		self.rtscts = False
		self.dsrdtr = False
		if self.__isMicropython:
			import machine
			self.__machine = machine
			self.__lowlevel = None

	def open(self):
		if self.__isMicropython:
			port = self.port
			for sub in ("/dev/ttyS", "/dev/ttyUSB", "/dev/ttyACM", "COM", ):
				port = port.replace(sub, "")
			try:
				port = int(port)
			except ValueError:
				raise SerialException("Invalid port: %s" % self.port)
			try:
				self.__lowlevel = self.__machine.UART(port, self.baudrate)
				self.__lowlevel.init(self.baudrate,
						     self.bytesize,
						     0 if self.parity == PARITY_EVEN else 1,
						     self.stopbits)
				print("Opened machine.UART(%d)" % port)
			except Exception as e:
				raise SerialException("Failed to open port '%s':\n%s" % (
					self.port, str(e)))
			return
		raise NotImplementedError

	def close(self):
		if self.__isMicropython:
			try:
				if self.__lowlevel is not None:
					self.__lowlevel.deinit()
				self.__lowlevel = None
			except Exception as e:
				raise SerialException("Failed to close port '%s':\n%s" % (
					self.port, str(e)))
			return
		raise NotImplementedError

	def write(self, data):
		if self.__isMicropython:
			try:
				self.__lowlevel.write(data)
			except Exception as e:
				raise SerialException("Write(%d bytes) failed: %s" % (
					len(data), str(e)))
			return
		raise NotImplementedError

	def read(self, size=1):
		if self.__isMicropython:
			try:
				data = self.__lowlevel.read(size)
				if data is None:
					return b""
				return data
			except Exception as e:
				raise SerialException("Read(%d bytes) failed: %s" % (
					size, str(e)))
		raise NotImplementedError
