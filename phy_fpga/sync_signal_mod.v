// vim: ts=4 sw=4 noexpandtab
/*
 *   Synchronize a signal to a clock
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

`ifndef SYNC_SIGNAL_MOD_V_
`define SYNC_SIGNAL_MOD_V_

module sync_signal(
	input clk,			/* clock */
	input in,			/* input signal */
	output out,			/* synchronized output signal */
	output falling,		/* synchronized falling edge output */
	output rising,		/* synchronized rising edge output */
);
	reg [2:0] shiftreg;

	initial begin
		shiftreg <= 0;
	end

	always @(posedge clk) begin
		shiftreg[2:1] <= shiftreg[1:0];
		shiftreg[0] <= in;
	end

	assign out = shiftreg[1];
	assign falling = shiftreg[2] & ~shiftreg[1];
	assign rising = ~shiftreg[2] & shiftreg[1];

endmodule

`endif /* SYNC_SIGNAL_MOD_V_ */
