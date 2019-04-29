#!/usr/bin/env python3
# vim: ts=8 sw=8 noexpandtab
#
#   CRC code generator
#
#   Copyright (c) 2019 Michael Buesch <m@bues.ch>
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License along
#   with this program; if not, write to the Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

from dataclasses import dataclass
import argparse
import sys


__all__ = [
	"CrcGen",
]


CRC_PARAMETERS = {
	"CRC-32" : {
		"polynomial"	: 0xEDB88320,
		"nrBits"	: 32,
		"shiftRight"	: True,
	},
	"CRC-16" : {
		"polynomial"	: 0xA001,
		"nrBits"	: 16,
		"shiftRight"	: True,
	},
	"CRC-16-CCITT" : {
		"polynomial"	: 0x1021,
		"nrBits"	: 16,
		"shiftRight"	: False,
	},
	"CRC-8-CCITT" : {
		"polynomial"	: 0x07,
		"nrBits"	: 8,
		"shiftRight"	: False,
	},
	"CRC-8-IBUTTON" : {
		"polynomial"	: 0x8C,
		"nrBits"	: 8,
		"shiftRight"	: True,
	},
}


class CrcReference(object):
	"""Generic CRC reference implementation.
	"""

	@classmethod
	def crc(cls, crc, data, polynomial, nrBits, shiftRight):
		mask = (1 << nrBits) - 1
		msb = 1 << (nrBits - 1)
		lsb = 1
		if shiftRight:
			tmp = (crc ^ data) & 0xFF
			for i in range(8):
				if tmp & lsb:
					tmp = ((tmp >> 1) ^ polynomial) & mask
				else:
					tmp = (tmp >> 1) & mask
			crc = ((crc >> 8) ^ tmp) & mask
		else:
			tmp = (crc ^ (data << (nrBits - 8))) & mask
			for i in range(8):
				if tmp & msb:
					tmp = ((tmp << 1) ^ polynomial) & mask
				else:
					tmp = (tmp << 1) & mask
			crc = tmp
		return crc

	@classmethod
	def crcBlock(cls, crc, data, polynomial, nrBits, shiftRight, preFlip, postFlip):
		mask = (1 << nrBits) - 1
		if preFlip:
			crc ^= mask
		for b in data:
			crc = cls.crc(crc, b, polynomial, nrBits, shiftRight)
		if postFlip:
			crc ^= mask
		return crc

@dataclass
class AbstractBit(object):
	def flatten(self):
		return self

	def optimize(self):
		pass

@dataclass
class Bit(AbstractBit):
	name: str
	index: int

	def gen_python(self):
		return "%s[%d]" % (self.name, self.index)

	def gen_c(self):
		if self.index:
			return "((%s >> %du) & 1u)" % (self.name, self.index)
		return "(%s & 1u)" % (self.name)

	def gen_verilog(self):
		return "%s[%d]" % (self.name, self.index)

@dataclass
class ConstBit(AbstractBit):
	value: int

	def gen_python(self):
		return "1" if self.value else "0"

	def gen_c(self):
		return "1u" if self.value else "0u"

	def gen_verilog(self):
		return "1'b1" if self.value else "1'b0"

class XOR(object):
	def __init__(self, *items):
		self.items = items

	def flatten(self):
		newItems = []
		for item in self.items:
			if isinstance(item, XOR):
				newItems.extend(item.flatten().items)
			else:
				newItems.append(item)
		self.items = newItems
		return self

	def optimize(self):
		newItems = []
		for item in self.items:
			if isinstance(item, ConstBit):
				if item.value == 0:
					# Constant 0 does not change the XOR result.
					# Remove it.
					pass
				else:
					# Keep it.
					newItems.append(item)
			elif isinstance(item, Bit):
				if item in newItems:
					# We already have this bit.
					# Remove it.
					pass
				else:
					if sum(1 if (isinstance(i, Bit) and i == item) else 0
					       for i in self.items) % 2:
						# We have an uneven count of this bit.
						# Keep it once.
						newItems.append(item)
					else:
						# An even amount cancels out in XOR.
						# Remove it.
						pass
			else:
				# This is something else.
				# Keep it.
				newItems.append(item)
		if not newItems:
			# All items have been optimized out.
			# This term shall be zero.
			newItems.append(ConstBit(0))
		self.items = newItems

	def gen_python(self):
		assert(self.items)
		return "(%s)" % (" ^ ".join(item.gen_python() for item in self.items))

	def gen_c(self):
		assert(self.items)
		return "(%s)" % (" ^ ".join(item.gen_c() for item in self.items))

	def gen_verilog(self):
		assert(self.items)
		return "(%s)" % (" ^ ".join(item.gen_verilog() for item in self.items))

class Word(object):
	def __init__(self, *items, MSBFirst=True):
		if MSBFirst:
			# Reverse items, so that it's always LSB-first.
			items = reversed(items)
		self.items = list(items)

	def __getitem__(self, index):
		return self.items[index]

	def flatten(self):
		self.items = [ item.flatten() for item in self.items ]

	def optimize(self):
		for item in self.items:
			item.optimize()

class CrcGenError(Exception):
	pass

class CrcGen(object):
	"""Combinatorial CRC algorithm generator.
	"""

	OPT_FLATTEN	= 1 << 0
	OPT_ELIMINATE	= 1 << 1

	OPT_NONE	= 0
	OPT_ALL		= OPT_FLATTEN | OPT_ELIMINATE

	def __init__(self,
		     P,
		     nrBits,
		     shiftRight=False,
		     optimize=OPT_ALL):
		self.__P = P
		self.__nrBits = nrBits
		self.__shiftRight = shiftRight
		self.__optimize = optimize

	def __gen(self, dataVarName, crcVarName):
		nrBits = self.__nrBits
		assert nrBits in (8, 16, 32), "Invalid nrBits"

		# Construct the function input data word.
		inData = Word(*(
			Bit(dataVarName, i)
			for i in reversed(range(8))
		))

		# Construct the function input CRC word.
		inCrc  = Word(*(
			Bit(crcVarName, i)
			for i in reversed(range(nrBits))
		))

		# Construct the base word.
		# This is the start word for the bit shifting loop below.
		if self.__shiftRight:
			base = Word(*(
				XOR(inData[i], inCrc[i]) if i <= 7 else ConstBit(0)
				for i in reversed(range(nrBits))
			))
		else:
			base = Word(*(
				XOR(inData[i - (nrBits - 8)] if i >= nrBits - 8 else ConstBit(0),
				    inCrc[i])
				for i in reversed(range(nrBits))
			))

		# Helper function to XOR a polynomial bit with the data bit 'dataBit',
		# if the decision bit 'queryBit' is set.
		# This is done reversed, because the polynomial is constant.
		def xor_P(dataBit, queryBit, bitNr):
			if (self.__P >> bitNr) & 1:
				return XOR(dataBit, queryBit)
			return dataBit

		# Run the main shift loop.
		prevWord = base
		for _ in range(8):
			if self.__shiftRight:
				# Shift to the right: i + 1
				word = Word(*(
					xor_P(prevWord[i + 1] if i < nrBits - 1 else ConstBit(0),
					      prevWord[0],
					      i)
					for i in reversed(range(nrBits))
				))
			else:
				# Shift to the left: i - 1
				word = Word(*(
					xor_P(prevWord[i - 1] if i > 0 else ConstBit(0),
					      prevWord[nrBits - 1],
					      i)
					for i in reversed(range(nrBits))
				))
			prevWord = word

		# Construct the function output CRC word.
		if self.__shiftRight:
			outCrc = Word(*(
				XOR(inCrc[i + 8] if i < nrBits - 8 else ConstBit(0),
				    word[i])
				for i in reversed(range(nrBits))
			))
		else:
			outCrc = word

		# Optimize the algorithm. This removes unnecessary operations.
		if self.__optimize & self.OPT_FLATTEN:
			outCrc.flatten()
		if self.__optimize & self.OPT_ELIMINATE:
			outCrc.optimize()

		return outCrc

	def __header(self):
		return """\
THIS IS GENERATED CODE.

This code is Public Domain.
Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER
RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE
USE OR PERFORMANCE OF THIS SOFTWARE."""

	def __algDescription(self):
		return ("CRC polynomial      = 0x%X (hex)\n"
			"CRC width           = %d bits\n"
			"CRC shift direction = %s\n" % (
			self.__P,
			self.__nrBits,
			"right" if self.__shiftRight else "left",
		))

	def genPython(self,
		      funcName="crc",
		      crcVarName="crc",
		      dataVarName="data"):
		word = self.__gen(dataVarName, crcVarName)
		ret = []
		ret.append("# vim: ts=8 sw=8 noexpandtab")
		ret.append("")
		ret.extend("# " + l for l in self.__header().splitlines())
		ret.append("")
		ret.extend("# " + l for l in self.__algDescription().splitlines())
		ret.append("")
		ret.append("def %s(%s, %s):" % (funcName, crcVarName, dataVarName))
		ret.append("\tclass bitwrapper:")
		ret.append("\t\tdef __init__(self, value):")
		ret.append("\t\t\tself.value = value")
		ret.append("\t\tdef __getitem__(self, index):")
		ret.append("\t\t\treturn ((self.value >> index) & 1)")
		ret.append("\t\tdef __setitem__(self, index, value):")
		ret.append("\t\t\tif value:")
		ret.append("\t\t\t\tself.value |= 1 << index")
		ret.append("\t\t\telse:")
		ret.append("\t\t\t\tself.value &= ~(1 << index)")
		ret.append("\t%s = bitwrapper(%s)" % (crcVarName, crcVarName))
		ret.append("\t%s = bitwrapper(%s)" % (dataVarName, dataVarName))
		ret.append("\tret = bitwrapper(0)")
		for i, bit in enumerate(word):
			ret.append("\tret[%d] = %s" % (i, bit.gen_python()))
		ret.append("\treturn ret.value")
		return "\n".join(ret)

	def genVerilog(self,
		       genFunction=True,
		       name="crc",
		       inDataName="inData",
		       inCrcName="inCrc",
		       outCrcName="outCrc"):
		word = self.__gen(inDataName, inCrcName)
		ret = []
		ret.append("// vim: ts=4 sw=4 noexpandtab")
		ret.append("")
		ret.extend("// " + l for l in self.__header().splitlines())
		ret.append("")
		if not genFunction:
			ret.append("`ifndef %s_V_" % name.upper())
			ret.append("`define %s_V_" % name.upper())
			ret.append("")
		ret.extend("// " + l for l in self.__algDescription().splitlines())
		ret.append("")
		if genFunction:
			ret.append("function automatic [%d:0] %s;" % (self.__nrBits - 1, name))
		else:
			ret.append("module %s (" % name)
		ret.append("\tinput [%d:0] %s%s" % (self.__nrBits - 1, inCrcName,
						    ";" if genFunction else ","))
		ret.append("\tinput [7:0] %s%s" % (inDataName,
						   ";" if genFunction else ","))
		if genFunction:
			ret.append("begin")
		else:
			ret.append("\toutput [%d:0] %s," % (self.__nrBits - 1, outCrcName))
			ret.append(");")
		for i, bit in enumerate(word):
			ret.append("\t%s%s[%d] = %s;" % ("" if genFunction else "assign ",
							 name if genFunction else outCrcName,
							 i, bit.gen_verilog()))
		if genFunction:
			ret.append("end")
			ret.append("endfunction")
		else:
			ret.append("endmodule")
			ret.append("")
			ret.append("`endif // %s_V_" % name.upper())
		return "\n".join(ret)

	def genC(self,
		 funcName="crc",
		 crcVarName="crc",
		 dataVarName="data",
		 static=False,
		 inline=False):
		word = self.__gen(dataVarName, crcVarName)
		cType = "uint%s_t" % self.__nrBits
		ret = []
		ret.append("// vim: ts=4 sw=4 noexpandtab")
		ret.append("")
		ret.extend("// " + l for l in self.__header().splitlines())
		ret.append("")
		ret.append("#ifndef %s_H_" % funcName.upper())
		ret.append("#define %s_H_" % funcName.upper())
		ret.append("")
		ret.append("#include <stdint.h>")
		ret.append("")
		ret.extend("// " + l for l in self.__algDescription().splitlines())
		ret.append("")
		ret.append("%s%s%s %s(%s %s, uint8_t %s)" % ("static " if static else "",
							     "inline " if inline else "",
							     cType,
							     funcName,
							     cType,
							     crcVarName,
							     dataVarName))
		ret.append("{")
		ret.append("\t%s ret;" % cType)
		for i, bit in enumerate(word):
			if i:
				operator = "|="
				shift = " << %du" % i
			else:
				operator = "="
				shift = ""
			ret.append("\tret %s (%s)%s;" % (operator, bit.gen_c(), shift))
		ret.append("\treturn ret;")
		ret.append("}")
		ret.append("")
		ret.append("#endif /* %s_H_ */" % funcName.upper())
		return "\n".join(ret)

	def runTests(self, name=None, extra=None):
		import random

		rng = random.Random()
		rng.seed(424242)

		print("Testing%s P=0x%X, nrBits=%d, shiftRight=%d %s..." % (
		      (" " + name) if name else "",
		      self.__P,
		      self.__nrBits,
		      int(bool(self.__shiftRight)),
		      (extra + " ") if extra else ""))

		# Generate the CRC function as Python code.
		pyCode = self.genPython(funcName="crc_func")
		execEnv = {}
		exec(pyCode, execEnv)
		crc_func = execEnv["crc_func"]

		mask = (1 << self.__nrBits) - 1
		for i in range(0xFF + 1):
			if i == 0:
				crc = 0
			elif i == 1:
				crc = mask
			else:
				crc = rng.randint(1, mask - 1)
			for data in range(0xFF + 1):
				a = CrcReference.crc(
					crc=crc,
					data=data,
					polynomial=self.__P,
					nrBits=self.__nrBits,
					shiftRight=self.__shiftRight)
				b = crc_func(crc, data)
				if a != b:
					raise CrcGenError("Test failed. "
						"(P=0x%X, nrBits=%d, shiftRight=%d, "
						"a=0x%X, b=0x%X)" % (
						self.__P, self.__nrBits,
						int(bool(self.__shiftRight)),
						a, b))

if __name__ == "__main__":
	try:
		def argInt(string):
			if string.startswith("0x"):
				return int(string[2:], 16)
			return int(string)
		p = argparse.ArgumentParser()
		g = p.add_mutually_exclusive_group(required=True)
		g.add_argument("-p", "--python", action="store_true", help="Generate Python code")
		g.add_argument("-v", "--verilog-function", action="store_true", help="Generate Verilog function")
		g.add_argument("-m", "--verilog-module", action="store_true", help="Generate Verilog module")
		g.add_argument("-c", "--c", action="store_true", help="Generate C code")
		g.add_argument("-t", "--test", action="store_true", help="Run unit tests for the specified algorithm")
		p.add_argument("-a", "--algorithm", type=str,
			       choices=CRC_PARAMETERS.keys(), default="CRC-8-CCITT",
			       help="Select the CRC algorithm. "
				    "Individual algorithm parameters (e.g. polynomial) can be overridden with the options below.")
		p.add_argument("-P", "--polynomial", type=argInt, help="CRC polynomial")
		p.add_argument("-B", "--nr-bits", type=argInt, choices=[8, 16, 32], help="Number of bits")
		g = p.add_mutually_exclusive_group()
		g.add_argument("-R", "--shift-right", action="store_true", help="CRC algorithm shift direction: right shift")
		g.add_argument("-L", "--shift-left", action="store_true", help="CRC algorithm shift direction: left shift")
		p.add_argument("-n", "--name", type=str, default="crc", help="Generated function/module name")
		p.add_argument("-D", "--data-param", type=str, default="data", help="Generated function/module data parameter name")
		p.add_argument("-C", "--crc-in-param", type=str, default="crcIn", help="Generated function/module crc input parameter name")
		p.add_argument("-o", "--crc-out-param", type=str, default="crcOut", help="Generated module crc output parameter name")
		p.add_argument("-S", "--static", action="store_true", help="Generate static C function")
		p.add_argument("-I", "--inline", action="store_true", help="Generate inline C function")
		p.add_argument("-O", "--optimize", type=argInt, default=CrcGen.OPT_ALL, help="Enable algorithm optimizer steps")
		args = p.parse_args()

		crcParameters = CRC_PARAMETERS[args.algorithm].copy()
		if args.polynomial is not None:
			crcParameters["polynomial"] = args.polynomial
		if args.nr_bits is not None:
			crcParameters["nrBits"] = args.nr_bits
		if args.shift_right:
			crcParameters["shiftRight"] = True
		if args.shift_left:
			crcParameters["shiftRight"] = False

		polynomial = crcParameters["polynomial"]
		nrBits = crcParameters["nrBits"]
		shiftRight = crcParameters["shiftRight"]

		if polynomial > ((1 << nrBits) - 1):
			raise CrcGenError("Invalid polynomial. "
					  "It is bigger than the CRC width "
					  "of (2**%d)-1." % nrBits)

		gen = CrcGen(P=polynomial,
			     nrBits=nrBits,
			     shiftRight=shiftRight,
			     optimize=args.optimize)
		if args.test:
			gen.runTests()
		else:
			if args.python:
				print(gen.genPython(funcName=args.name,
						    crcVarName=args.crc_in_param,
						    dataVarName=args.data_param))
			elif args.verilog_function:
				print(gen.genVerilog(genFunction=True,
						     name=args.name,
						     inDataName=args.data_param,
						     inCrcName=args.crc_in_param,
						     outCrcName=args.crc_out_param))
			elif args.verilog_module:
				print(gen.genVerilog(genFunction=False,
						     name=args.name,
						     inDataName=args.data_param,
						     inCrcName=args.crc_in_param,
						     outCrcName=args.crc_out_param))
			elif args.c:
				print(gen.genC(funcName=args.name,
					       crcVarName=args.crc_in_param,
					       dataVarName=args.data_param,
					       static=args.static,
					       inline=args.inline))
		sys.exit(0)
	except CrcGenError as e:
		print("ERROR: %s" % str(e), file=sys.stderr)
		sys.exit(1)
