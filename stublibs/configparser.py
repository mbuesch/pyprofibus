class Error(Exception):
	pass

class ConfigParser(object):
	class Section(object):
		def __init__(self, name):
			self.name = name
			self.options = {}

	def __init__(self):
		self.__sections = {}

	def read_file(self, f, source=None):
		self.__sections = {}
		sectionName = ""
		data = f.read()
		for line in data.splitlines():
			line = line.lstrip()
			if not line or line.startswith(";"):
				continue
			if line.startswith("["):
				sectionName = line.strip().replace("[", "").replace("]", "")
				self.__sections[sectionName] = self.Section(sectionName)
				continue
			if not sectionName:
				raise Error("Option is not in section.")
			idx = line.find("=")
			if idx > 0:
				optionName = line[:idx]
				optionValue = line[idx+1:]
				self.__sections[sectionName].options[optionName] = optionValue
				continue
			raise Error("Could not parse line.")

	def has_option(self, section, option):
		try:
			self.get(section, option)
		except Error as e:
			return False
		return True

	def get(self, section, option):
		try:
			return self.__sections[section].options[option]
		except KeyError as e:
			raise Error("Option not found.")

	def getboolean(self, section, option):
		try:
			v = self.get(section, option).lower().strip()
			if v == "true":
				return True
			if v == "false":
				return False
			return bool(int(v))
		except ValueError as e:
			raise Error("Invalid boolean option.")

	def getint(self, section, option):
		try:
			return int(self.get(section, option))
		except ValueError as e:
			raise Error("Invalid int option.")

	def sections(self):
		return list(self.__sections.keys())

	def options(self, section):
		try:
			return list(self.__sections[section].options)
		except KeyError as e:
			raise Error("Section not found.")
