// vim: ts=4 sw=4 noexpandtab
/*
 *   UART
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

`ifndef UART_MOD_V_
`define UART_MOD_V_

`include "sync_signal_mod.v"
`include "edge_detect_mod.v"


`ifndef UART_DEFAULT_DATABITS
`define UART_DEFAULT_DATABITS		8
`endif

`ifndef UART_DEFAULT_PARITY_EVEN
`define UART_DEFAULT_PARITY_EVEN	0
`endif

`ifndef UART_DEFAULT_STOP
`define UART_DEFAULT_STOP			2
`endif

`ifndef UART_DEFAULT_ACTIVE_LOW
`define UART_DEFAULT_ACTIVE_LOW		0
`endif


/* UART symbol clock generator */
module uart_symclk (
	input clk,					/* Clock */
	input n_reset,				/* Not reset */
	input [23:0] clks_per_sym,	/* Number of clocks per UART symbol */
	output reg setup,			/* Setup edge (leading) */
	output reg sample,			/* Setup point (center) */
	output reg symend,			/* End edge (trailing) */
);
	localparam CLKS_PER_SYM_MIN = 4; /* lower limit for clks_per_sym */

	reg [23:0] count;
	wire [23:0] clks_per_sym_limited;
	wire [23:0] clks_per_sym_half;

	assign clks_per_sym_limited = (clks_per_sym >= CLKS_PER_SYM_MIN) ? clks_per_sym : CLKS_PER_SYM_MIN;
	assign clks_per_sym_half = clks_per_sym_limited >> 1;

	initial begin
		count <= 0;
		setup <= 0;
		sample <= 0;
		symend <= 0;
	end

	always @(posedge clk) begin
		if (n_reset) begin
			if (count == 0) begin
				count <= count + 1;
				setup <= 1;
				sample <= 0;
				symend <= 0;
			end else if (count == clks_per_sym_half - 1) begin
				count <= count + 1;
				setup <= 0;
				sample <= 1;
				symend <= 0;
			end else if (count >= clks_per_sym_limited - 1) begin
				count <= 0;
				setup <= 0;
				sample <= 0;
				symend <= 1;
			end else begin
				count <= count + 1;
				setup <= 0;
				sample <= 0;
				symend <= 0;
			end
		end else begin
			count <= 0;
			setup <= 0;
			sample <= 0;
			symend <= 0;
		end
	end
endmodule


/* UART receiver */
module uart_rx #(
	parameter DATABITS			= `UART_DEFAULT_DATABITS,
	parameter PARITY_EVEN		= `UART_DEFAULT_PARITY_EVEN,
	parameter ACTIVE_LOW		= `UART_DEFAULT_ACTIVE_LOW,
) (
	input clk,								/* Clock */
	input n_reset,							/* Not reset */
	input [23:0] clks_per_sym,				/* Number of clocks per UART symbol */
	input rx,								/* Synchronized(!) receive signal line */
	output reg rx_irq,						/* Data received interrupt */
	output reg rx_active,					/* Receive in progress */
	output reg [DATABITS - 1 : 0] rx_data,	/* Received data */
	output reg rx_parity,					/* Received parity bit */
	output reg rx_parity_ok,				/* Received parity Ok? */
	output reg rx_frame_error,				/* Received frame had an error? */
);
	`include "parity_func.v"

	localparam COUNT_START_WAIT	= 0;
	localparam COUNT_START		= COUNT_START_WAIT + 1;
	localparam COUNT_BIT0		= COUNT_START + 1;
	localparam COUNT_BIT1		= COUNT_BIT0 + ((DATABITS >= 2) ? 1 : 0);
	localparam COUNT_BIT2		= COUNT_BIT1 + ((DATABITS >= 3) ? 1 : 0);
	localparam COUNT_BIT3		= COUNT_BIT2 + ((DATABITS >= 4) ? 1 : 0);
	localparam COUNT_BIT4		= COUNT_BIT3 + ((DATABITS >= 5) ? 1 : 0);
	localparam COUNT_BIT5		= COUNT_BIT4 + ((DATABITS >= 6) ? 1 : 0);
	localparam COUNT_BIT6		= COUNT_BIT5 + ((DATABITS >= 7) ? 1 : 0);
	localparam COUNT_BIT7		= COUNT_BIT6 + ((DATABITS >= 8) ? 1 : 0);
	localparam COUNT_BIT8		= COUNT_BIT7 + ((DATABITS >= 9) ? 1 : 0);
	localparam COUNT_PARITY		= COUNT_BIT8 + 1;
	localparam COUNT_STOP0		= COUNT_PARITY + 1;

	/* Receive signal. */
	wire rx_sig;
	wire rx_start;
	wire rx_falling;
	assign rx_sig = ACTIVE_LOW ? ~rx : rx;
	edge_detect rx_edge(.clk(clk), .signal(rx_sig), .falling(rx_falling));

	/* State machine */
	reg [3:0] sym_count;
	reg [DATABITS - 1 : 0] rx_buf;
	reg rx_parity_buf;
	reg rx_frame_error_start;

	/* Symbol clock */
	reg symclk_n_reset;
	wire symclk_sample;
	wire symclk_end;
	uart_symclk symclk (
		.clk(clk),
		.n_reset(symclk_n_reset),
		.clks_per_sym(clks_per_sym),
		.sample(symclk_sample),
		.symend(symclk_end),
	);

	/* Parity calculation */
	wire calc_rx_parity;
	assign calc_rx_parity = parity9(PARITY_EVEN ? EVEN : ODD,
									(DATABITS >= 1) ? rx_buf[0] : 0,
									(DATABITS >= 2) ? rx_buf[1] : 0,
									(DATABITS >= 3) ? rx_buf[2] : 0,
									(DATABITS >= 4) ? rx_buf[3] : 0,
									(DATABITS >= 5) ? rx_buf[4] : 0,
									(DATABITS >= 6) ? rx_buf[5] : 0,
									(DATABITS >= 7) ? rx_buf[6] : 0,
									(DATABITS >= 8) ? rx_buf[7] : 0,
									(DATABITS >= 9) ? rx_buf[8] : 0);

	initial begin
		rx_irq <= 0;
		rx_active <= 0;
		rx_data <= 0;
		rx_parity <= 0;
		rx_parity_ok <= 0;
		rx_frame_error <= 0;

		symclk_n_reset <= 0;
		sym_count <= COUNT_START_WAIT;
		rx_buf <= 0;
		rx_parity_buf <= 0;
		rx_frame_error_start <= 0;
	end

	always @(posedge clk) begin
		if (n_reset) begin
			if (sym_count == COUNT_START_WAIT) begin /* Waiting for start edge */
				if (rx_falling) begin
					symclk_n_reset <= 1;
					sym_count <= sym_count + 1;
					rx_buf <= 0;
					rx_active <= 1;
				end
				rx_irq <= 0;
			end else if (sym_count == COUNT_START) begin /* Start bit */
				if (symclk_sample) begin
					rx_frame_error_start <= rx_sig;
				end else if (symclk_end) begin
					sym_count <= sym_count + 1;
				end
			end else if ((sym_count == COUNT_BIT0) || /* Bit 0 */
				     (sym_count == COUNT_BIT1) || /* Bit 1 */
				     (sym_count == COUNT_BIT2) || /* Bit 2 */
				     (sym_count == COUNT_BIT3) || /* Bit 3 */
				     (sym_count == COUNT_BIT4) || /* Bit 4 */
				     (sym_count == COUNT_BIT5) || /* Bit 5 */
				     (sym_count == COUNT_BIT6) || /* Bit 6 */
				     (sym_count == COUNT_BIT7) || /* Bit 7 */
				     (sym_count == COUNT_BIT8)) begin /* Bit 8 */
				if (symclk_sample) begin
					rx_buf[sym_count - COUNT_BIT0] = rx_sig;
				end else if (symclk_end) begin
					sym_count <= sym_count + 1;
				end
			end else if (sym_count == COUNT_PARITY) begin /* Parity */
				if (symclk_sample) begin
					rx_parity_buf = rx_sig;
				end else if (symclk_end) begin
					sym_count <= sym_count + 1;
				end
			end else if (sym_count == COUNT_STOP0) begin /* Stop 0 */
				if (symclk_sample) begin
					rx_data <= rx_buf;
					rx_parity <= calc_rx_parity;
					rx_parity_ok <= (calc_rx_parity == rx_parity_buf);
					rx_frame_error <= rx_frame_error_start | ~rx_sig;
					rx_irq <= 1;
					rx_active <= 0;

					sym_count <= COUNT_START_WAIT;
					symclk_n_reset <= 0;
				end
			end else begin
				symclk_n_reset <= 0;
				sym_count <= COUNT_START_WAIT;
				rx_irq <= 0;
				rx_active <= 0;
			end
		end else begin
			symclk_n_reset <= 0;
			sym_count <= COUNT_START_WAIT;
			rx_irq <= 0;
			rx_active <= 0;
		end
	end
endmodule


/* UART transmitter */
module uart_tx #(
	parameter DATABITS					= `UART_DEFAULT_DATABITS,
	parameter PARITY_EVEN				= `UART_DEFAULT_PARITY_EVEN,
	parameter STOP						= `UART_DEFAULT_STOP,
	parameter ACTIVE_LOW				= `UART_DEFAULT_ACTIVE_LOW,
) (
	input clk,							/* Clock */
	input n_reset,						/* Not reset */
	input [23:0] clks_per_sym,			/* Number of clocks per UART symbol */
	output tx,							/* Raw transmit signal line */
	output reg tx_irq,					/* Data transmitted interrupt */
	output reg tx_active,				/* Transmit in progress */
	input [DATABITS - 1 : 0] tx_data,	/* Transmit data */
	input tx_trigger,					/* Start transmission (only if not tx_active). */
);
	`include "parity_func.v"

	localparam COUNT_START_WAIT	= 0;
	localparam COUNT_START		= COUNT_START_WAIT + 1;
	localparam COUNT_BIT0		= COUNT_START + 1;
	localparam COUNT_BIT1		= COUNT_BIT0 + ((DATABITS >= 2) ? 1 : 0);
	localparam COUNT_BIT2		= COUNT_BIT1 + ((DATABITS >= 3) ? 1 : 0);
	localparam COUNT_BIT3		= COUNT_BIT2 + ((DATABITS >= 4) ? 1 : 0);
	localparam COUNT_BIT4		= COUNT_BIT3 + ((DATABITS >= 5) ? 1 : 0);
	localparam COUNT_BIT5		= COUNT_BIT4 + ((DATABITS >= 6) ? 1 : 0);
	localparam COUNT_BIT6		= COUNT_BIT5 + ((DATABITS >= 7) ? 1 : 0);
	localparam COUNT_BIT7		= COUNT_BIT6 + ((DATABITS >= 8) ? 1 : 0);
	localparam COUNT_BIT8		= COUNT_BIT7 + ((DATABITS >= 9) ? 1 : 0);
	localparam COUNT_PARITY		= COUNT_BIT8 + 1;
	localparam COUNT_STOP0		= COUNT_PARITY + 1;
	localparam COUNT_STOP1		= COUNT_STOP0 + ((STOP >= 2) ? 1 : 0);

	/* Output buffer. */
	reg tx_r;
	assign tx = ACTIVE_LOW ? ~tx_r : tx_r;

	/* State machine */
	reg [3:0] sym_count;
	reg [DATABITS - 1 : 0] tx_buf;

	/* Symbol clock */
	reg symclk_n_reset;
	wire symclk_setup;
	wire symclk_sample;
	wire symclk_end;
	uart_symclk symclk (
		.clk(clk),
		.n_reset(symclk_n_reset),
		.clks_per_sym(clks_per_sym),
		.setup(symclk_setup),
		.sample(symclk_sample),
		.symend(symclk_end),
	);

	/* Parity calculation */
	wire calc_tx_parity;
	assign calc_tx_parity = parity9(PARITY_EVEN ? EVEN : ODD,
									(DATABITS >= 1) ? tx_buf[0] : 0,
									(DATABITS >= 2) ? tx_buf[1] : 0,
									(DATABITS >= 3) ? tx_buf[2] : 0,
									(DATABITS >= 4) ? tx_buf[3] : 0,
									(DATABITS >= 5) ? tx_buf[4] : 0,
									(DATABITS >= 6) ? tx_buf[5] : 0,
									(DATABITS >= 7) ? tx_buf[6] : 0,
									(DATABITS >= 8) ? tx_buf[7] : 0,
									(DATABITS >= 9) ? tx_buf[8] : 0);

	initial begin
		tx_r <= 1;
		tx_irq <= 0;
		tx_active <= 0;

		symclk_n_reset <= 0;
	end

	always @(posedge clk) begin
		if (n_reset) begin
			if (sym_count == COUNT_START_WAIT) begin
				if (tx_trigger) begin
					symclk_n_reset <= 1;
					sym_count <= sym_count + 1;
					tx_buf <= tx_data;
					tx_active <= 1;
				end
				tx_r <= 1;
				tx_irq <= 0;
			end else if (sym_count == COUNT_START) begin /* Start bit */
				if (symclk_end) begin
					sym_count <= sym_count + 1;
				end
				tx_r <= 0;
			end else if ((sym_count == COUNT_BIT0) || /* Bit 0 */
				     (sym_count == COUNT_BIT1) || /* Bit 1 */
				     (sym_count == COUNT_BIT2) || /* Bit 2 */
				     (sym_count == COUNT_BIT3) || /* Bit 3 */
				     (sym_count == COUNT_BIT4) || /* Bit 4 */
				     (sym_count == COUNT_BIT5) || /* Bit 5 */
				     (sym_count == COUNT_BIT6) || /* Bit 6 */
				     (sym_count == COUNT_BIT7) || /* Bit 7 */
				     (sym_count == COUNT_BIT8)) begin /* Bit 8 */
				if (symclk_setup) begin
					tx_r <= tx_buf[sym_count - COUNT_BIT0];
				end else if (symclk_end) begin
					sym_count <= sym_count + 1;
				end
			end else if (sym_count == COUNT_PARITY) begin /* Parity */
				if (symclk_setup) begin
					tx_r <= calc_tx_parity;
				end else if (symclk_end) begin
					sym_count <= sym_count + 1;
				end
			end else if (sym_count == COUNT_STOP0 && STOP >= 1) begin /* Stop 0 */
				if (symclk_setup) begin
					tx_r <= 1;
				end else if (symclk_end) begin
					if (STOP >= 2) begin
						sym_count <= sym_count + 1;
					end else begin
						symclk_n_reset <= 0;
						sym_count <= COUNT_START_WAIT;
						tx_irq <= 1;
						tx_active <= 0;
					end
				end
			end else if (sym_count == COUNT_STOP1 && STOP >= 2) begin /* Stop 1 */
				if (symclk_setup) begin
					tx_r <= 1;
				end else if (symclk_end) begin
					symclk_n_reset <= 0;
					sym_count <= COUNT_START_WAIT;
					tx_irq <= 1;
					tx_active <= 0;
				end
			end else begin
				symclk_n_reset <= 0;
				sym_count <= COUNT_START_WAIT;
				tx_r <= 1;
				tx_irq <= 0;
				tx_active <= 0;
			end
		end else begin
			symclk_n_reset <= 0;
			sym_count <= COUNT_START_WAIT;
			tx_r <= 1;
			tx_irq <= 0;
			tx_active <= 0;
		end
	end
endmodule


/* UART full duplex transceiver */
module uart_full_duplex #(
	parameter DATABITS					= `UART_DEFAULT_DATABITS,
	parameter PARITY_EVEN				= `UART_DEFAULT_PARITY_EVEN,
	parameter STOP						= `UART_DEFAULT_STOP,
	parameter ACTIVE_LOW				= `UART_DEFAULT_ACTIVE_LOW,
) (
	input clk,							/* Clock */
	input n_reset,						/* Not reset */
	input [23:0] clks_per_sym,			/* Number of clocks per UART symbol */
	input rx,							/* Raw receive signal line */
	output rx_irq,						/* Data received interrupt */
	output rx_active,					/* Receive in progress */
	output [DATABITS - 1 : 0] rx_data,	/* Received data */
	output rx_parity,					/* Received parity bit */
	output rx_parity_ok,				/* Received parity Ok? */
	output rx_frame_error,				/* Received frame had an error? */
	output tx,							/* Raw transmit signal line */
	output tx_irq,						/* Data transmitted interrupt */
	output tx_active,					/* Transmit in progress */
	input [DATABITS - 1 : 0] tx_data,	/* Transmit data */
	input tx_trigger,					/* Start transmission (only if not tx_active). */
);
	/* Synchronized receive signal. */
	wire rx_s;
	sync_signal sync_rx(.clk(clk), .in(rx), .out(rx_s));

	uart_rx #(
		.DATABITS(DATABITS),
		.PARITY_EVEN(PARITY_EVEN),
		.ACTIVE_LOW(ACTIVE_LOW),
	) rx_mod (
		.clk(clk),
		.n_reset(n_reset),
		.clks_per_sym(clks_per_sym),
		.rx(rx_s),
		.rx_irq(rx_irq),
		.rx_active(rx_active),
		.rx_data(rx_data),
		.rx_parity(rx_parity),
		.rx_parity_ok(rx_parity_ok),
		.rx_frame_error(rx_frame_error),
	);

	uart_tx #(
		.DATABITS(DATABITS),
		.PARITY_EVEN(PARITY_EVEN),
		.STOP(STOP),
		.ACTIVE_LOW(ACTIVE_LOW),
	) tx_mod (
		.clk(clk),
		.n_reset(n_reset),
		.clks_per_sym(clks_per_sym),
		.tx(tx),
		.tx_irq(tx_irq),
		.tx_active(tx_active),
		.tx_data(tx_data),
		.tx_trigger(tx_trigger),
	);
endmodule


/* UART half duplex bus arbiter */
module uart_arbiter #(
	parameter ACTIVE_LOW		= `UART_DEFAULT_ACTIVE_LOW,
) (
	input clk,					/* Clock */
	input rx,					/* Receive signal line */
	input tx_active,			/* Transmit in progress */
	output tx_allowed,			/* Transmit allowed now? */
	input rx_active,			/* Receive in progress */
	output rx_allowed,			/* Receive allowed now? */
);
	wire rx_sig;
	assign rx_sig = ACTIVE_LOW ? ~rx : rx;

	/* Allow TX if:
	 *  - No RX is currently active AND
	 *  - The RX line is idle */
	assign tx_allowed = ~rx_active & rx_sig;

	/* Allow RX, if TX is currenly not active. */
	assign rx_allowed = ~tx_active;
endmodule


/* UART half duplex transceiver */
module uart_half_duplex #(
	parameter DATABITS					= `UART_DEFAULT_DATABITS,
	parameter PARITY_EVEN				= `UART_DEFAULT_PARITY_EVEN,
	parameter STOP						= `UART_DEFAULT_STOP,
	parameter ACTIVE_LOW				= `UART_DEFAULT_ACTIVE_LOW,
) (
	input clk,							/* Clock */
	input n_reset,						/* Not reset */
	input [23:0] clks_per_sym,			/* Number of clocks per UART symbol */
	input rx,							/* Raw receive signal line */
	output rx_irq,						/* Data received interrupt */
	output rx_active,					/* Receive in progress */
	output [DATABITS - 1 : 0] rx_data,	/* Received data */
	output rx_parity,					/* Received parity bit */
	output rx_parity_ok,				/* Received parity Ok? */
	output rx_frame_error,				/* Received frame had an error? */
	output tx,							/* Raw transmit signal line */
	output tx_irq,						/* Data transmitted interrupt */
	output tx_active,					/* Transmit in progress */
	output tx_pending,					/* Start of transmission requested, but currenly blocked. */
	input [DATABITS - 1 : 0] tx_data,	/* Transmit data */
	input tx_trigger,					/* Start transmission (only if not tx_active). */
);
	/* Synchronized receive signal. */
	wire rx_s;
	sync_signal sync_rx(.clk(clk), .in(rx), .out(rx_s));

	wire arb_tx_allowed;
	wire arb_rx_active;
	wire arb_rx_allowed;
	uart_arbiter #(
		.ACTIVE_LOW(ACTIVE_LOW),
	) arb_mod (
		.clk(clk),
		.rx(rx_s),
		.tx_active(tx_active_w),
		.tx_allowed(arb_tx_allowed),
		.rx_active(arb_rx_active),
		.rx_allowed(arb_rx_allowed),
	);

	wire rx_n_reset;
	assign rx_n_reset = n_reset & arb_rx_allowed;
	assign rx_active = arb_rx_active;
	uart_rx #(
		.DATABITS(DATABITS),
		.PARITY_EVEN(PARITY_EVEN),
		.ACTIVE_LOW(ACTIVE_LOW),
	) rx_mod (
		.clk(clk),
		.n_reset(rx_n_reset),
		.clks_per_sym(clks_per_sym),
		.rx(rx_s),
		.rx_irq(rx_irq),
		.rx_active(arb_rx_active),
		.rx_data(rx_data),
		.rx_parity(rx_parity),
		.rx_parity_ok(rx_parity_ok),
		.rx_frame_error(rx_frame_error),
	);

	reg tx_trigger_req;
	reg [DATABITS - 1 : 0] tx_data_r;
	wire tx_n_reset;
	wire tx_active_w;
	assign tx_n_reset = n_reset & (arb_tx_allowed | tx_active_w);
	assign tx_pending = tx_trigger_req;
	assign tx_active = tx_active_w;
	uart_tx #(
		.DATABITS(DATABITS),
		.PARITY_EVEN(PARITY_EVEN),
		.STOP(STOP),
		.ACTIVE_LOW(ACTIVE_LOW),
	) tx_mod (
		.clk(clk),
		.n_reset(tx_n_reset),
		.clks_per_sym(clks_per_sym),
		.tx(tx),
		.tx_irq(tx_irq),
		.tx_active(tx_active_w),
		.tx_data(tx_data_r),
		.tx_trigger(tx_trigger_req),
	);

	initial begin
		tx_trigger_req <= 0;
		tx_data_r <= 0;
	end

	always @(posedge clk) begin
		if (n_reset) begin
			if (tx_trigger_req) begin
				if (arb_tx_allowed & ~tx_active_w & tx_n_reset) begin
					tx_trigger_req <= 0;
					tx_data_r <= 0;
				end
			end else begin
				/* If TX has been requested, store the request
				 * so that it can be serviced after a possibly running
				 * RX or TX transmission has finished. */
				if (tx_trigger) begin
					tx_trigger_req <= 1;
					tx_data_r <= tx_data;
				end
			end
		end else begin
			tx_trigger_req <= 0;
			tx_data_r <= 0;
		end
	end
endmodule


`endif /* UART_MOD_V_ */
