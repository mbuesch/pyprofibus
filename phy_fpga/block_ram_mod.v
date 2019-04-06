// vim: ts=4 sw=4 noexpandtab
/*
 *   Block RAM
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

`ifndef BLOCK_RAM_MOD_V_
`define BLOCK_RAM_MOD_V_


module block_ram #(
	parameter ADDR_WIDTH	= 16,
	parameter DATA_WIDTH	= 8,
	parameter MEM_BYTES		= 1024,
) (
	input							clk,
	/* Port 0 */
	input	   [ADDR_WIDTH - 1 : 0]	addr0,
	output reg [DATA_WIDTH - 1 : 0]	rd_data0,
	input	   [DATA_WIDTH - 1 : 0]	wr_data0,
	input							wr0,
	/* Port 1 */
	input	   [ADDR_WIDTH - 1 : 0]	addr1,
	output reg [DATA_WIDTH - 1 : 0]	rd_data1,
);
	reg [DATA_WIDTH - 1 : 0] mem [MEM_BYTES - 1 : 0];
	integer i;

	initial begin
		for (i = 0; i < MEM_BYTES; i++) begin
			mem[i] <= 0;
		end
	end

	always @(posedge clk) begin
		if (wr0) begin
			mem[addr0] <= wr_data0;
		end
		rd_data0 <= mem[addr0];
		rd_data1 <= mem[addr1];
	end
endmodule


`endif /* BLOCK_RAM_MOD_V_ */
