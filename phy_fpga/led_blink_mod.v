// vim: ts=4 sw=4 noexpandtab
/*
 *   LED blinker
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

`ifndef LED_BLINK_MOD_V_
`define LED_BLINK_MOD_V_


module led_blink #(
	parameter BLINK_ON_CLKS		= 1024,
	parameter BLINK_OFF_CLKS	= 1024,
) (
	input clk,
	input n_reset,
	input enable,
	output reg led,
);
	reg [31:0] led_on_count;
	reg [31:0] led_off_count;

	initial begin
		led <= 0;
		led_on_count <= 0;
		led_off_count <= 0;
	end

	always @(posedge clk) begin
		if (n_reset) begin
			if (led) begin
				if (led_on_count == 0) begin
					led <= 0;
					led_off_count <= BLINK_OFF_CLKS;
				end else begin
					led_on_count <= led_on_count - 1;
				end
			end else begin
				if (led_off_count == 0) begin
					if (enable) begin
						led <= 1;
						led_on_count <= BLINK_ON_CLKS;
					end
				end else begin
					led_off_count <= led_off_count - 1;
				end
			end
		end else begin
			led <= 0;
			led_on_count <= 0;
			led_off_count <= 0;
		end
	end
endmodule

`endif /* LED_BLINK_MOD_V_ */
