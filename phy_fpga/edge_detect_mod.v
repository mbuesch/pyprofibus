// vim: ts=4 sw=4 noexpandtab
/*
 *   Edge detection
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

`ifndef EDGE_DETECT_MOD_V_
`define EDGE_DETECT_MOD_V_


module edge_detect #(
	parameter NR_BITS = 1,					/* Number of bits */
) (
	input wire clk,							/* Clock */
	input wire [NR_BITS - 1 : 0] signal,	/* Input signal */
	output wire [NR_BITS - 1 : 0] rising,	/* Rising edge detected on input signal */
	output wire [NR_BITS - 1 : 0] falling,	/* Falling edge detected on input signal */
);
	reg [NR_BITS - 1 : 0] prev_signal;

	always @(posedge clk) begin
		prev_signal <= signal;
	end

	assign rising = ~prev_signal & signal;
	assign falling = prev_signal & ~signal;
endmodule


`endif /* EDGE_DETECT_MOD_V_ */
