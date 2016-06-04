# -*- coding: utf-8 -*-
#
# Python compatibility
#
# Copyright 2012-2016 Michael Buesch <m@bues.ch>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

from __future__ import division, absolute_import, print_function, unicode_literals

import sys


# isPy3Compat is True, if the interpreter is Python 3 compatible.
isPy3Compat = sys.version_info[0] == 3

# isPy2Compat is True, if the interpreter is Python 2 compatible.
isPy2Compat = sys.version_info[0] == 2

# input() compatibility.
# Force Python3 behavior
if isPy2Compat:
	input = raw_input

# range() compatibility.
# Force Python3 behavior
if isPy2Compat:
	range = xrange

# reduce() compatibility.
# Force Python2 behavior
if isPy3Compat:
	from functools import reduce

# BlockingIOError dummy
try:
	BlockingIOError
except NameError:
	class BlockingIOError(BaseException): pass

# ConnectionError dummy
try:
	ConnectionError
except NameError:
	ConnectionError = OSError
