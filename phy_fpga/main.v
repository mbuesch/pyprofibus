// vim: ts=4 sw=4 noexpandtab
/*
 *   pyprofibus FPGA PHY
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

`include "profibus_phy_mod.v"


`ifdef TARGET_TINYFPGA_BX

module top_module(
	input CLK,
	input SPI_SS,
	input SPI_SCK,
	input SPI_IO0,
	input SPI_IO1,
	input SPI_IO2,
	input SPI_IO3,
	input USBP,
	input USBN,
	output USBPU,
	output LED,
	output PIN_1,
	input PIN_2,
	input PIN_3,
	input PIN_4,
	input PIN_5,
	input PIN_6,
	input PIN_7,
	input PIN_8,
	input PIN_9,
	input PIN_10,
	input PIN_11,
	output PIN_12,
	input PIN_13,
	input PIN_14,
	output PIN_15,
	output PIN_16,
	output PIN_17,
	input PIN_18,
	input PIN_19,
	input PIN_20,
	input PIN_21,
	output PIN_22,
	output PIN_23,
	input PIN_24,
	input PIN_25,
	input PIN_26,
	input PIN_27,
	input PIN_28,
	input PIN_29,
	input PIN_30,
	input PIN_31,
);
	wire pb_rx_active;
	wire pb_tx_active;
	profibus_phy pb(
		.clk(CLK),
		.n_reset(PIN_19),
		.rx_irq_edge(PIN_22),
		.rx_irq_level(PIN_23),
		.mosi(PIN_13),
		.miso(PIN_12),
//		.miso_outen(),
		.sck(PIN_11),
		.ss(PIN_10),
		.rx(PIN_14),
		.rx_active(pb_rx_active),
		.rx_error(PIN_16),
		.tx(PIN_15),
		.tx_active(pb_tx_active),
		.tx_error(PIN_17),
		.debug(PIN_1),
	);
	assign LED = pb_tx_active | pb_rx_active;


	assign USBPU = 0; // Disable USB
endmodule

`else /* TARGET */
`ERROR____TARGET_is_not_known
`endif /* TARGET */
