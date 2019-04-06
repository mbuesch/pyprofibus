// vim: ts=4 sw=4 noexpandtab
/*
 *   Parity calculation
 *
 *   Copyright (c) 2019 Michael Buesch <m@bues.ch>
 *
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU General Public License as published by
 *   the Free Software Foundation; either version 2 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU General Public License for more details.
 *
 *   You should have received a copy of the GNU General Public License along
 *   with this program; if not, write to the Free Software Foundation, Inc.,
 *   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */


localparam EVEN = 0;
localparam ODD = 1;

function automatic parity9;
	input odd;
	input a;
	input b;
	input c;
	input d;
	input e;
	input f;
	input g;
	input h;
	input i;

	begin
		parity9 = odd ^ a ^ b ^ c ^ d ^ e ^ f ^ g ^ h ^ i;
	end
endfunction

function automatic parity8;
	input odd;
	input a;
	input b;
	input c;
	input d;
	input e;
	input f;
	input g;
	input h;

	begin
		parity8 = parity9(odd, a, b, c, d, e, f, g, h, 0);
	end
endfunction
