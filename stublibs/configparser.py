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
		section = None
		while True:
			line = f.readline()
			if not line:
				break
			line = line.lstrip().rstrip("\r\n")
			if not line or line.startswith(";"):
				continue
			sline = line.strip()
			if sline.startswith("[") and sline.endswith("]"):
				sectionName = sline[1:-1]
				if sectionName in self.__sections:
					raise Error("Multiple definitions of section '%s'" % sectionName)
				section = self.__sections[sectionName] = self.Section(sectionName)
				continue
			if section is None:
				raise Error("Option '%s' is not in a section." % line)
			idx = line.find("=")
			if idx > 0:
				optionName = line[:idx]
				optionValue = line[idx+1:]
				if optionName in section.options:
					raise Error("Multiple definitions of option '%s/%s'" % (
						section.name, optionName))
				section.options[optionName] = optionValue
				continue
			raise Error("Could not parse line: %s" % line)

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
			raise Error("Option '%s/%s' not found." % (section, option))

	def getboolean(self, section, option):
		try:
			v = self.get(section, option).lower().strip()
			if v == "true":
				return True
			if v == "false":
				return False
			return bool(int(v))
		except ValueError as e:
			raise Error("Invalid boolean option '%s/%s'." % (section, option))

	def getint(self, section, option):
		try:
			return int(self.get(section, option))
		except ValueError as e:
			raise Error("Invalid int option '%s/%s'." % (section, option))

	def sections(self):
		return list(self.__sections.keys())

	def options(self, section):
		try:
			return list(self.__sections[section].options)
		except KeyError as e:
			raise Error("Section '%s' not found." % section)
