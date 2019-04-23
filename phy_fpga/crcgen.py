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
		if self.index:
			return "((%s >> %d) & 1)" % (self.name, self.index)
		return "(%s & 1)" % (self.name)

	gen_c = gen_python

	def gen_verilog(self):
		return "%s[%d]" % (self.name, self.index)

@dataclass
class ConstBit(AbstractBit):
	value: int

	def gen_python(self):
		return "1" if self.value else "0"

	gen_c = gen_python

	def gen_verilog(self):
		return "1b1" if self.value else "1b0"

class XOR(object):
	def __init__(self, *items):
		self._items = items
		assert(len(self._items) >= 2)

	def flatten(self):
		newItems = []
		for item in self._items:
			if isinstance(item, XOR):
				newItems.extend(item.flatten()._items)
			else:
				newItems.append(item)
		self._items = newItems
		return self

	def optimize(self):
		newItems = []
		for item in self._items:
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
					       for i in self._items) % 2:
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
		self._items = newItems

	def gen_python(self):
		string = " ^ ".join(item.gen_python() for item in self._items)
		return "(%s)" % string

	def gen_c(self):
		string = " ^ ".join(item.gen_c() for item in self._items)
		return "(%s)" % string

	def gen_verilog(self):
		string = " ^ ".join(item.gen_verilog() for item in self._items)
		return "(%s)" % string

class Word(object):
	def __init__(self, *bits, MSBFirst=True):
		if len(bits) == 1 and isinstance(bits[0], (list, tuple)):
			bits = bits[0]
		if MSBFirst:
			bits = reversed(bits)
		self._items = list(bits)

	def __getitem__(self, index):
		return self._items[index]

	def flatten(self):
		newItems = []
		for item in self._items:
			newItems.append(item.flatten())
		self._items = newItems

	def optimize(self):
		for item in self._items:
			item.optimize()

class CrcGenError(Exception):
	pass

class CrcGen(object):
	"""Combinatorial CRC algorithm generator.
	"""

	OPT_FLATTEN	= 1 << 0
	OPT_ELIMINATE	= 1 << 1
	OPT_ALL		= OPT_FLATTEN | OPT_ELIMINATE

	def __init__(self,
		     P=0x07,
		     nrBits=8,
		     shiftRight=False,
		     optimize=OPT_ALL):
		self.__P = P
		self.__nrBits = nrBits
		self.__shiftRight = shiftRight
		self.__optimize = optimize

	def __gen(self, dataVarName, crcVarName):
		nrBits = self.__nrBits
		assert nrBits in (8, 16, 32), "Invalid nrBits"

		inData = Word(*(
			Bit(dataVarName, i)
			for i in reversed(range(8))
		))
		inCrc  = Word(*(
			Bit(crcVarName, i)
			for i in reversed(range(nrBits))
		))

		if self.__shiftRight:
			base = Word(*(
				XOR(inData[i], inCrc[i]) if i <= 7 else ConstBit(0)
				for i in reversed(range(nrBits))
			))
		else:
			base = Word(*(
				XOR(inData[i] if i <= 7 else ConstBit(0),
				    inCrc[i])
				for i in reversed(range(nrBits))
			))

		def xor_P(a, b, bitNr):
			if (self.__P >> bitNr) & 1:
				return XOR(a, b)
			return a

		prevWord = base
		for _ in range(8):
			if self.__shiftRight:
				word = Word(*(
					xor_P(prevWord[i + 1] if i < nrBits - 1 else ConstBit(0),
					      prevWord[0],
					      i)
					for i in reversed(range(nrBits))
				))
			else:
				word = Word(*(
					xor_P(prevWord[i - 1] if i > 0 else ConstBit(0),
					      prevWord[nrBits - 1],
					      i)
					for i in reversed(range(nrBits))
				))
			prevWord = word

		if self.__shiftRight:
			result = Word(*(
				XOR(inCrc[i + 8] if i < nrBits - 8 else ConstBit(0),
				    word[i])
				for i in reversed(range(nrBits))
			))
		else:
			result = word

		# Optimize the algorithm. This removes unnecessary operations.
		if self.__optimize & self.OPT_FLATTEN:
			result.flatten()
		if self.__optimize & self.OPT_ELIMINATE:
			result.optimize()

		return result

	def __header(self):
		return ("THIS IS GENERATED CODE.\n"
			"This code is Public Domain.\n"
			"It can be used without any restrictions.\n")

	def genPython(self,
		      funcName="crc",
		      crcVarName="crc",
		      dataVarName="data"):
		word = self.__gen(dataVarName, crcVarName)
		ret = []
		ret.append("# vim: ts=8 sw=8 noexpandtab")
		ret.extend("# " + l for l in self.__header().splitlines())
		ret.append("")
		ret.append("# polynomial = 0x%X" % self.__P)
		ret.append("def %s(%s, %s):" % (funcName, crcVarName, dataVarName))
		for i, bit in enumerate(word):
			if i:
				operator = "|="
				shift = " << %d" % i
			else:
				operator = "="
				shift = ""
			ret.append("\tret %s (%s)%s" % (operator, bit.gen_python(), shift))
		ret.append("\treturn ret")
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
		ret.extend("// " + l for l in self.__header().splitlines())
		ret.append("")
		if not genFunction:
			ret.append("`ifndef %s_V_" % name.upper())
			ret.append("`define %s_V_" % name.upper())
			ret.append("")
		ret.append("// polynomial = 0x%X" % self.__P)
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
		ret.extend("// " + l for l in self.__header().splitlines())
		ret.append("")
		ret.append("#ifndef %s_H_" % funcName.upper())
		ret.append("#define %s_H_" % funcName.upper())
		ret.append("")
		ret.append("#include <stdint.h>")
		ret.append("")
		ret.append("// polynomial = 0x%X" % self.__P)
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
				shift = " << %d" % i
			else:
				operator = "="
				shift = ""
			ret.append("\tret %s (%s)%s;" % (operator, bit.gen_c(), shift))
		ret.append("\treturn ret;")
		ret.append("}")
		ret.append("")
		ret.append("#endif /* %s_H_ */" % funcName.upper())
		return "\n".join(ret)

if __name__ == "__main__":
	def crc_reference(crc, data, P, nrBits, shiftRight, preFlip, postFlip):
		mask = (1 << nrBits) - 1
		msb = 1 << (nrBits - 1)
		lsb = 1
		if preFlip:
			crc ^= mask
		for b in data:
			if shiftRight:
				tmp = (crc ^ b) & 0xFF
				for i in range(8):
					if tmp & lsb:
						tmp = ((tmp >> 1) ^ P) & mask
					else:
						tmp = (tmp >> 1) & mask
				crc = ((crc >> 8) ^ tmp) & mask
			else:
				tmp = (crc ^ (b << (nrBits - 8))) & mask
				for i in range(8):
					if tmp & msb:
						tmp = ((tmp << 1) ^ P) & mask
					else:
						tmp = (tmp << 1) & mask
				crc = tmp
		if postFlip:
			crc ^= mask
		return crc

	def runTests(crc_func, polynomial, nrBits, shiftRight):
		import random

		rng = random.Random()
		rng.seed(424242)

		print("Testing...")
		mask = (1 << nrBits) - 1
		for i in range(0x400):
			if i == 0:
				crc = 0
			elif i == 1:
				crc = mask
			else:
				crc = rng.randint(1, mask - 1)
			for data in range(0xFF + 1):
				a = crc_reference(crc=crc,
						  data=(data,),
						  P=polynomial,
						  nrBits=nrBits,
						  shiftRight=shiftRight,
						  preFlip=False,
						  postFlip=False)
				b = crc_func(crc, data)
				if a != b:
					raise CrcGenError("Test failed. "
						"(P=0x%X, nrBits=%d, shiftRight=%d, "
						"a=0x%X, b=0x%X)" % (
						polynomial, nrBits, int(shiftRight),
						a, b))
		print("done.")

	try:
		def argInt(string):
			if string.startswith("0x"):
				return int(string[2:], 16)
			return int(string)
		p = argparse.ArgumentParser()
		g = p.add_mutually_exclusive_group()
		g.add_argument("-p", "--python", action="store_true", help="Generate Python code")
		g.add_argument("-v", "--verilog-function", action="store_true", help="Generate Verilog function")
		g.add_argument("-m", "--verilog-module", action="store_true", help="Generate Verilog module")
		g.add_argument("-c", "--c", action="store_true", help="Generate C code")
		p.add_argument("-P", "--polynomial", type=argInt, default=0x07, help="CRC polynomial")
		p.add_argument("-B", "--nr-bits", type=argInt, choices=[8, 16, 32], default=8, help="Number of bits")
		p.add_argument("-R", "--shift-right", action="store_true", help="CRC algorithm shift direction")
		p.add_argument("-n", "--name", type=str, default="crc", help="Generated function/module name")
		p.add_argument("-D", "--data-param", type=str, default="data", help="Generated function/module data parameter name")
		p.add_argument("-C", "--crc-in-param", type=str, default="crcIn", help="Generated function/module crc input parameter name")
		p.add_argument("-o", "--crc-out-param", type=str, default="crcOut", help="Generated module crc output parameter name")
		p.add_argument("-S", "--static", action="store_true", help="Generate static C function")
		p.add_argument("-I", "--inline", action="store_true", help="Generate inline C function")
		p.add_argument("-O", "--optimize", type=argInt, default=CrcGen.OPT_ALL, help="Enable algorithm optimizer steps")
		p.add_argument("-T", "--test", action="store_true", help="Run unit tests")
		args = p.parse_args()

		if (not (args.polynomial >> (args.nr_bits - 1 if args.shift_right else 0) & 1) or
		    args.polynomial > ((1 << args.nr_bits) - 1)):
			raise CrcGenError("Invalid polynomial.")
		gen = CrcGen(P=args.polynomial,
			     nrBits=args.nr_bits,
			     shiftRight=args.shift_right,
			     optimize=args.optimize)
		if args.test:
			pyCode = gen.genPython(funcName="crc_func")
			exec(pyCode)
			runTests(crc_func=crc_func,
				 polynomial=args.polynomial,
				 nrBits=args.nr_bits,
				 shiftRight=args.shift_right)
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
