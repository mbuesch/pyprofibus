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


`ifdef DEBUG
`define DEBUGOUT output
`else
`define DEBUGOUT input
`endif


module common_main_module #(
	parameter CLK_HZ = 0,
) (
	input clk,
	input n_reset,

	/* SPI bus */
	input spi_mosi,
	inout spi_miso,
	input spi_sck,
	input spi_ss,

	/* Profibus and status */
	input pb_rx,
	output pb_rx_error,
	output pb_rx_irq_edge,
	output pb_rx_irq_level,
	output pb_tx,
	output pb_tx_active,
	output pb_tx_error,

	/* Status and debugging */
	output led,
`ifdef DEBUG
	output debug,
`endif
);
	wire miso;
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

	bufif0(spi_miso,		miso,			spi_ss);
	bufif0(pb_rx_error,		rx_error,		0);
	bufif0(pb_rx_irq_edge,	rx_irq_edge,	0);
	bufif0(pb_rx_irq_level,	rx_irq_level,	0);
	bufif0(pb_tx,			tx,				0);
	bufif0(pb_tx_active,	tx_active,		0);
	bufif0(pb_tx_error,		tx_error,		0);
`ifdef DEBUG
	bufif0(debug,			debug_w,		0);
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
	bufif0(led, led_w, 0);
endmodule


`ifdef TARGET_TINYFPGA_BX

`include "pll_mod.v"

/* TinyFPGA BX:
 *               +---------------+
 *               |P|GND     Vin|P|
 *     not reset |O|1       GND|P|
 *         debug |D|2      3.3V|P|
 *               |N|3    T   24|N|
 *               |N|4    i   23|N|
 *               |N|5    n   22|N|
 *               |N|6    y   21|N|
 *               |N|7    F   20|O| PB RX IRQ level
 *               |N|8    P   19|O| PB RX IRQ edge
 *               |N|9    G   18|O| PB TX error
 *      SPI MISO |O|10   A   17|O| PB RX error
 *      SPI MOSI |I|11       16|O| PB TX active
 *       SPI SCK |I|12   B   15|O| PB UART TX
 *        SPI SS |I|13   X   14|I| PB UART RX
 *               +---------------+
 * P = power
 * I = input
 * O = output
 * D = debug output. Only if DEBUG is enabled. Otherwise N.
 * N = not connected
 */
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
	input PIN_1,
	`DEBUGOUT PIN_2,
	input PIN_3,
	input PIN_4,
	input PIN_5,
	input PIN_6,
	input PIN_7,
	input PIN_8,
	input PIN_9,
	inout PIN_10,
	input PIN_11,
	input PIN_12,
	input PIN_13,
	input PIN_14,
	output PIN_15,
	output PIN_16,
	output PIN_17,
	output PIN_18,
	output PIN_19,
	output PIN_20,
	input PIN_21,
	input PIN_22,
	input PIN_23,
	input PIN_24,
	input PIN_25,
	input PIN_26,
	input PIN_27,
	input PIN_28,
	input PIN_29,
	input PIN_30,
	input PIN_31,
);

	wire pll_clk_out;
	wire pll_locked;

	pll_module pll(
		.clock_in(CLK),
		.clock_out(pll_clk_out),
		.locked(pll_locked),
	);

	wire n_reset;
	assign n_reset = PIN_1 & pll_locked;

	common_main_module #(
		.CLK_HZ(`PLL_HZ),
	) common (
		.clk(pll_clk_out),
		.n_reset(n_reset),
		.spi_mosi(PIN_11),
		.spi_miso(PIN_10),
		.spi_sck(PIN_12),
		.spi_ss(PIN_13),
		.pb_rx(PIN_14),
		.pb_rx_error(PIN_17),
		.pb_rx_irq_edge(PIN_19),
		.pb_rx_irq_level(PIN_20),
		.pb_tx(PIN_15),
		.pb_tx_active(PIN_16),
		.pb_tx_error(PIN_18),
		.led(LED),
`ifdef DEBUG
		.debug(PIN_2),
`endif
	);

	assign USBPU = 0; /* Disable USB */
endmodule

`else /* TARGET */
`ERROR____TARGET_is_not_known
`endif /* TARGET */
