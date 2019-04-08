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
`include "led_blink_mod.v"


module common_main_module #(
	parameter CLK_HZ = 0,
) (
	input clk,
	input n_reset,

	/* SPI bus */
	input spi_mosi,
	output spi_miso,
	output spi_miso_outen,
	input spi_sck,
	input spi_ss,

	/* Profibus and status */
	input pb_rx,
	output pb_rx_error,
	output pb_rx_irq_edge,
	output pb_rx_irq_level,
	output pb_tx,
	output pb_tx_error,

	/* Status and debugging */
	output led,
`ifdef DEBUG
	output debug,
`endif
);
	wire miso;
	wire miso_outen;
	wire sck;
	wire ss;
	wire rx_error;
	wire rx_irq_edge;
	wire rx_irq_level;
	wire tx;
	wire tx_error;
	wire rx_active;
	wire tx_active;
`ifdef DEBUG
	wire debug_w;
`endif

	profibus_phy pb(
		.clk(clk),
		.n_reset(n_reset),
		.rx_irq_edge(rx_irq_edge),
		.rx_irq_level(rx_irq_level),
		.mosi(spi_mosi),
		.miso(miso),
		.miso_outen(miso_outen),
		.sck(spi_sck),
		.ss(spi_ss),
		.rx(pb_rx),
		.rx_active(rx_active),
		.rx_error(rx_error),
		.tx(tx),
		.tx_active(tx_active),
		.tx_error(tx_error),
`ifdef DEBUG
		.debug(debug_w),
`endif
	);

	bufif1(spi_miso,		miso,			miso_outen);
	bufif1(spi_miso_outen,	miso_outen,		1);
	bufif1(pb_rx_error,		rx_error,		1);
	bufif1(pb_rx_irq_edge,	rx_irq_edge,	1);
	bufif1(pb_rx_irq_level,	rx_irq_level,	1);
	bufif1(pb_tx,			tx,				1);
	bufif1(pb_tx_error,		tx_error,		1);
`ifdef DEBUG
	bufif1(debug,			debug_w,		1);
`endif

	wire led_w;
	wire led_enable;
	assign led_enable = tx_active | rx_active;

	led_blink #(
		.BLINK_ON_CLKS(CLK_HZ / 10),
		.BLINK_OFF_CLKS(CLK_HZ / 35),
	) led_blink (
		.clk(clk),
		.n_reset(n_reset),
		.enable(led_enable),
		.led(led_w),
	);
	bufif1(led, led_w, 1);
endmodule


`ifdef TARGET_TINYFPGA_BX

/* TinyFPGA BX */
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
`ifndef DEBUG
	input PIN_1,
`else
	output PIN_1,
`endif
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
	common_main_module #(
		.CLK_HZ(16000000),
	) common (
		.clk(CLK),
		.n_reset(PIN_19),
		.spi_mosi(PIN_13),
		.spi_miso(PIN_12),
//TODO	.spi_miso_outen(),
		.spi_sck(PIN_11),
		.spi_ss(PIN_10),
		.pb_rx(PIN_14),
		.pb_rx_error(PIN_16),
		.pb_rx_irq_edge(PIN_22),
		.pb_rx_irq_level(PIN_23),
		.pb_tx(PIN_15),
		.pb_tx_error(PIN_17),
		.led(LED),
`ifdef DEBUG
		.debug(PIN_1),
`endif
	);

	assign USBPU = 0; /* Disable USB */
endmodule

`else /* TARGET */
`ERROR____TARGET_is_not_known
`endif /* TARGET */
