from pyprofibus.compat import *
import time

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
		self.__portNum = None
		self.baudrate = 9600
		self.bytesize = 8
		self.parity = PARITY_EVEN
		self.stopbits = STOPBITS_ONE
		self.timeout = 0
		self.xonxoff = False
		self.rtscts = False
		self.dsrdtr = False
		self.__lowlevel = None

	def open(self):
		if self.__isMicropython:
			port = self.port
			for sub in ("/dev/ttyS", "/dev/ttyUSB", "/dev/ttyACM", "COM", "UART", ):
				port = port.replace(sub, "")
			try:
				self.__portNum = int(port.strip())
			except ValueError:
				raise SerialException("Invalid port: %s" % self.port)
			try:
				import machine
				self.__lowlevel = machine.UART(
					self.__portNum,
					self.baudrate,
					self.bytesize,
					0 if self.parity == PARITY_EVEN else 1,
					1 if self.stopbits == STOPBITS_ONE else 2)
				print("Opened machine.UART(%d)" % self.__portNum)
			except Exception as e:
				raise SerialException("UART%d: Failed to open:\n%s" % (
					self.__portNum, str(e)))
			return
		raise NotImplementedError

	def close(self):
		if self.__isMicropython:
			try:
				if self.__lowlevel is not None:
					self.__lowlevel.deinit()
					self.__lowlevel = None
					print("Closed machine.UART(%d)" % self.__portNum)
			except Exception as e:
				raise SerialException("UART%d: Failed to close:\n%s" % (
					self.__portNum, str(e)))
			return
		raise NotImplementedError

	def write(self, data):
		if self.__isMicropython:
			try:
				self.__lowlevel.write(data)
			except Exception as e:
				raise SerialException("UART%d write(%d bytes) failed: %s" % (
					self.__portNum, len(data), str(e)))
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
				raise SerialException("UART%d read(%d bytes) failed: %s" % (
					self.__portNum, size, str(e)))
		raise NotImplementedError

	def flushInput(self):
		if self.__isMicropython:
			while self.__lowlevel.any():
				self.__lowlevel.read()
			return
		raise NotImplementedError

	def flushOutput(self):
		if self.__isMicropython:
			time.sleep(0.01)
			return
		raise NotImplementedError
