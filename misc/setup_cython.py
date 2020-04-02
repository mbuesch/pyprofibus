#
#   Cython patcher
#   v1.21
#
#   Copyright (C) 2012-2020 Michael Buesch <m@bues.ch>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from __future__ import print_function

import sys
import os
import platform
import errno
import shutil
import hashlib
import re

WORKER_MEM_BYTES	= 800 * 1024*1024
WORKER_CPU_OVERCOMMIT	= 2

setupFileName = "setup.py"
parallelBuild = False
profileEnabled = False
debugEnabled = False
ext_modules = []
CythonBuildExtension = None

patchDirName = "cython_patched.%s-%s-%d.%d" % (
		platform.system().lower(),
		platform.machine().lower(),
		sys.version_info[0],
		sys.version_info[1])

_Cython_Distutils_build_ext = None
_cythonPossible = None
_cythonBuildUnits = []
_isWindows = os.name.lower() in {"nt", "ce"}
_isPosix = os.name.lower() == "posix"


def getSystemMemBytesCount():
	try:
		with open("/proc/meminfo", "rb") as fd:
			for line in fd.read().decode("UTF-8", "ignore").splitlines():
				if line.startswith("MemTotal:") and\
				   line.endswith("kB"):
					kB = int(line.split()[1], 10)
					return kB * 1024
	except (OSError, IndexError, ValueError, UnicodeError) as e:
		pass
	if hasattr(os, "sysconf"):
		try:
			return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
		except ValueError as e:
			pass
	return None

def makedirs(path, mode=0o755):
	try:
		os.makedirs(path, mode)
	except OSError as e:
		if e.errno == errno.EEXIST:
			return
		raise e

def hashFile(path):
	try:
		with open(path, "rb") as fd:
			return hashlib.sha1(fd.read()).hexdigest()
	except FileNotFoundError as e:
		return None

def __fileopIfChanged(fromFile, toFile, fileops):
	toFileHash = hashFile(toFile)
	if toFileHash is not None:
		fromFileHash = hashFile(fromFile)
		if toFileHash == fromFileHash:
			return False
	makedirs(os.path.dirname(toFile))
	for fileop in fileops:
		fileop(fromFile, toFile)
	return True

def removeFile(filename):
	try:
		os.unlink(filename)
	except OSError:
		pass

def copyIfChanged(fromFile, toFile):
	fileops = []
	if _isWindows:
		fileops.append(lambda _fromFile, _toFile: removeFile(_toFile))
	fileops.append(shutil.copy2)
	return __fileopIfChanged(fromFile, toFile, fileops)

def moveIfChanged(fromFile, toFile):
	fileops = []
	if _isWindows:
		fileops.append(lambda _fromFile, _toFile: removeFile(_toFile))
	fileops.append(os.rename)
	return __fileopIfChanged(fromFile, toFile, fileops)

def makeDummyFile(path):
	if os.path.isfile(path):
		return
	print("creating dummy file '%s'" % path)
	makedirs(os.path.dirname(path))
	with open(path, "wb") as fd:
		fd.write("\n".encode("UTF-8"))

def pyCythonPatchLine(line):
	return line

def pyCythonPatch(fromFile, toFile):
	print("cython-patch: patching file '%s' to '%s'" %\
	      (fromFile, toFile))
	tmpFile = toFile + ".TMP"
	makedirs(os.path.dirname(tmpFile))
	with open(fromFile, "rb") as infd,\
	     open(tmpFile, "wb") as outfd:
		for line in infd.read().decode("UTF-8").splitlines(True):
			stripLine = line.strip()

			if stripLine.endswith("#@no-cython-patch"):
				outfd.write(line.encode("UTF-8"))
				continue

			# Replace import by cimport as requested by #+cimport
			if "#+cimport" in stripLine:
				line = line.replace("#+cimport", "#")
				line = re.sub(r'\bimport\b', "cimport", line)

			# Convert None to NULL
			if "#+NoneToNULL" in stripLine:
				line = line.replace("#+NoneToNULL", "#")
				line = re.sub(r'\bNone\b', "NULL", line)

			# Uncomment all lines containing #@cy
			def uncomment(line, removeStr):
				line = line.replace(removeStr, "")
				if line.startswith("#"):
					line = line[1:]
				if not line.endswith("\n"):
					line += "\n"
				return line
			if "#@cy-posix" in stripLine:
				if _isPosix:
					line = uncomment(line, "#@cy-posix")
			elif "#@cy-win" in stripLine:
				if _isWindows:
					line = uncomment(line, "#@cy-win")
			elif "#@cy" in stripLine:
				line = uncomment(line, "#@cy")

			# Sprinkle magic cdef/cpdef, as requested by #+cdef/#+cpdef
			if "#+cdef-" in stripLine:
				# +cdef-foo-bar is the extended cdef patching.
				# It adds cdef and any additional characters to the
				# start of the line. Dashes are replaced with spaces.

				# Get the additional text
				idx = line.find("#+cdef-")
				cdefText = line[idx+2 : ]
				cdefText = cdefText.replace("-", " ").rstrip("\r\n")

				# Get the initial space length
				spaceCnt = 0
				while spaceCnt < len(line) and line[spaceCnt].isspace():
					spaceCnt += 1

				# Construct the new line
				line = line[ : spaceCnt] + cdefText + " " + line[spaceCnt : ]
			elif "#+cdef" in stripLine:
				# Simple cdef patching:
				# def -> cdef
				# class -> cdef class

				if stripLine.startswith("class"):
					line = re.sub(r'\bclass\b', "cdef class", line)
				else:
					line = re.sub(r'\bdef\b', "cdef", line)
			if "#+cpdef" in stripLine:
				# Simple cpdef patching:
				# def -> cpdef

				line = re.sub(r'\bdef\b', "cpdef", line)

			# Add likely()/unlikely() to if-conditions.
			for likely in ("likely", "unlikely"):
				if "#+" + likely in stripLine:
					line = re.sub(r'\bif\s(.*):', r'if ' + likely + r'(\1):', line)
					break

			# Add an "u" suffix to decimal and hexadecimal numbers.
			if "#+suffix-u" in line or "#+suffix-U" in line:
				line = re.sub(r'\b([0-9]+)\b', r'\1u', line)
				line = re.sub(r'\b(0x[0-9a-fA-F]+)\b', r'\1u', line)

			# Add an "LL" suffix to decimal and hexadecimal numbers.
			if "#+suffix-ll" in line or "#+suffix-LL" in line:
				line = re.sub(r'\b(\-?[0-9]+)\b', r'\1LL', line)
				line = re.sub(r'\b(0x[0-9a-fA-F]+)\b', r'\1LL', line)

			# Comment all lines containing #@nocy
			if "#@nocy" in stripLine:
				line = "#" + line

			# Comment all lines containing #@cy-posix/win
			# for the not matching platform.
			if _isPosix:
				if "#@cy-win" in stripLine:
					line = "#" + line
			elif _isWindows:
				if "#@cy-posix" in stripLine:
					line = "#" + line

			# Remove compat stuff
			line = line.replace("absolute_import,", "")

			line = pyCythonPatchLine(line)

			outfd.write(line.encode("UTF-8"))
		outfd.flush()
	if moveIfChanged(tmpFile, toFile):
		print("(updated)")
	else:
		os.unlink(tmpFile)

class CythonBuildUnit(object):
	def __init__(self, cyModName, baseName, fromPy, fromPxd, toDir, toPyx, toPxd):
		self.cyModName = cyModName
		self.baseName = baseName
		self.fromPy = fromPy
		self.fromPxd = fromPxd
		self.toDir = toDir
		self.toPyx = toPyx
		self.toPxd = toPxd

def patchCythonModules(buildDir):
	for unit in _cythonBuildUnits:
		makedirs(unit.toDir)
		makeDummyFile(os.path.join(unit.toDir, "__init__.py"))
		if unit.baseName == "__init__":
			# Copy and patch the package __init__.py
			toPy = os.path.join(buildDir, *unit.cyModName.split(".")) + ".py"
			pyCythonPatch(unit.fromPy, toPy)
		else:
			# Generate the .pyx
			pyCythonPatch(unit.fromPy, unit.toPyx)
		# Copy and patch the .pxd, if any
		if os.path.isfile(unit.fromPxd):
			pyCythonPatch(unit.fromPxd, unit.toPxd)

def registerCythonModule(baseDir, sourceModName):
	global ext_modules
	global _cythonBuildUnits

	modDir = os.path.join(baseDir, sourceModName)
	# Make path to the cython patch-build-dir
	patchDir = os.path.join(baseDir, "build", patchDirName,
				("%s_cython" % sourceModName))

	if not os.path.exists(os.path.join(baseDir, setupFileName)) or\
	   not os.path.exists(modDir) or\
	   not os.path.isdir(modDir):
		raise Exception("Wrong directory. "
			"Execute setup.py from within the main directory.")

	# Walk the module
	for dirpath, dirnames, filenames in os.walk(modDir):
		subpath = os.path.relpath(dirpath, modDir)
		if subpath == baseDir:
			subpath = ""

		dirpathList = dirpath.split(os.path.sep)

		if any(os.path.exists(os.path.sep.join(dirpathList[:i] + ["no_cython"]))
		       for i in range(len(dirpathList) + 1)):
			# no_cython file exists. -> skip
			continue

		for filename in filenames:
			if filename.endswith(".py"):
				fromSuffix = ".py"
			elif filename.endswith(".pyx.in"):
				fromSuffix = ".pyx.in"
			else:
				continue

			baseName = filename[:-len(fromSuffix)] # Strip .py/.pyx.in

			fromPy = os.path.join(dirpath, baseName + fromSuffix)
			fromPxd = os.path.join(dirpath, baseName + ".pxd.in")
			toDir = os.path.join(patchDir, subpath)
			toPyx = os.path.join(toDir, baseName + ".pyx")
			toPxd = os.path.join(toDir, baseName + ".pxd")

			# Construct the new cython module name
			cyModName = [ "%s_cython" % sourceModName ]
			if subpath:
				cyModName.extend(subpath.split(os.sep))
			cyModName.append(baseName)
			cyModName = ".".join(cyModName)

			# Remember the filenames for the build
			unit = CythonBuildUnit(cyModName, baseName, fromPy, fromPxd,
					       toDir, toPyx, toPxd)
			_cythonBuildUnits.append(unit)

			if baseName != "__init__":
				# Create a distutils Extension for the module
				extra_compile_args = []
				extra_link_args = []
				if not _isWindows:
					extra_compile_args.append("-Wall")
					extra_compile_args.append("-Wextra")
					#extra_compile_args.append("-Wcast-qual")
					extra_compile_args.append("-Wlogical-op")
					extra_compile_args.append("-Wpointer-arith")
					extra_compile_args.append("-Wundef")
					extra_compile_args.append("-Wno-cast-function-type")
					extra_compile_args.append("-Wno-maybe-uninitialized")
					extra_compile_args.append("-Wno-type-limits")
					if debugEnabled:
						# Enable debugging and UBSAN.
						extra_compile_args.append("-g3")
						extra_compile_args.append("-fsanitize=undefined")
						extra_compile_args.append("-fsanitize=float-divide-by-zero")
						extra_compile_args.append("-fsanitize=float-cast-overflow")
						extra_compile_args.append("-fno-sanitize-recover")
						extra_link_args.append("-lubsan")
					else:
						# Disable all debugging symbols.
						extra_compile_args.append("-g0")
						extra_link_args.append("-Wl,--strip-all")
				ext_modules.append(
					_Cython_Distutils_Extension(
						cyModName,
						[toPyx],
						cython_directives={
							# Enable profile hooks?
							"profile"	: profileEnabled,
							"linetrace"	: profileEnabled,
							# Warn about unused variables?
							"warn.unused"	: False,
							# Set language version
							"language_level" : 3,
						},
						define_macros=[
							("CYTHON_TRACE",	str(int(profileEnabled))),
							("CYTHON_TRACE_NOGIL",	str(int(profileEnabled))),
						],
						include_dirs=[
							os.path.join("libs", "cython_headers"),
						],
						extra_compile_args=extra_compile_args,
						extra_link_args=extra_link_args
					)
				)

def registerCythonModules(baseDir=None):
	if baseDir is None:
		baseDir = os.curdir
	for filename in os.listdir(baseDir):
		if os.path.isdir(os.path.join(baseDir, filename)) and\
		   os.path.exists(os.path.join(baseDir, filename, "__init__.py")) and\
		   not os.path.exists(os.path.join(baseDir, filename, "no_cython")):
			registerCythonModule(baseDir, filename)

def cythonBuildPossible():
	global _cythonPossible

	if _cythonPossible is not None:
		return _cythonPossible

	_cythonPossible = False

	if sys.version_info[0] < 3:
		print("WARNING: Could not build the CYTHON modules: "
		      "Cython 2 not supported. Please use Cython 3.")
		return False

	try:
		import Cython.Compiler.Options
		# Omit docstrings in cythoned modules.
		Cython.Compiler.Options.docstrings = False
		# Generate module exit cleanup code.
		Cython.Compiler.Options.generate_cleanup_code = True
		# Generate HTML outputs.
		Cython.Compiler.Options.annotate = True

		from Cython.Distutils import build_ext, Extension
		global _Cython_Distutils_build_ext
		global _Cython_Distutils_Extension
		_Cython_Distutils_build_ext = build_ext
		_Cython_Distutils_Extension = Extension
	except ImportError as e:
		print("WARNING: Could not build the CYTHON modules: "
		      "%s" % str(e))
		print("--> Is Cython installed?")
		return False

	_cythonPossible = True
	return True

def cyBuildWrapper(arg):
	# This function does the same thing as the for-loop-body
	# inside of Cython's build_ext.build_extensions() method.
	# It is called via multiprocessing to build extensions
	# in parallel.
	# Note that this might break, if Cython's build_extensions()
	# is changed and stuff is added to its for loop. Meh.
	self, ext = arg
	ext.sources = self.cython_sources(ext.sources, ext)
	self.build_extension(ext)

if cythonBuildPossible():
	# Override Cython's build_ext class.
	class CythonBuildExtension(_Cython_Distutils_build_ext):
		class Error(Exception): pass

		def build_extension(self, ext):
			assert(not ext.name.endswith("__init__"))
			_Cython_Distutils_build_ext.build_extension(self, ext)

		def build_extensions(self):
			global parallelBuild

			# First patch the files, the run the build
			patchCythonModules(self.build_lib)

			if parallelBuild:
				# Run the parallel build, yay.
				try:
					self.check_extensions_list(self.extensions)

					# Calculate the number of worker processes to use.
					memBytes = getSystemMemBytesCount()
					if memBytes is None:
						raise self.Error("Unknown system memory size")
					print("System memory detected: %d MB" % (memBytes // (1024*1024)))
					memProcsMax = memBytes // WORKER_MEM_BYTES
					if memProcsMax < 2:
						raise self.Error("Not enough system memory")
					import multiprocessing
					numProcs = min(multiprocessing.cpu_count() + WORKER_CPU_OVERCOMMIT,
						       memProcsMax)

					# Start the worker pool.
					print("Building in parallel with %d workers." % numProcs)
					from multiprocessing.pool import Pool
					Pool(numProcs).map(cyBuildWrapper,
							   ((self, ext) for ext in self.extensions))
				except (OSError, self.Error) as e:
					# OSError might happen in a restricted
					# environment like chroot.
					print("WARNING: Parallel build "
					      "disabled due to: %s" % str(e))
					parallelBuild = False
			if not parallelBuild:
				# Run the normal non-parallel build.
				_Cython_Distutils_build_ext.build_extensions(self)
