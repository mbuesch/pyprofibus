// vim: ts=4 sw=4 noexpandtab
/*
 *   SPI bus slave
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

`ifndef SPI_SLAVE_MOD_V_
`define SPI_SLAVE_MOD_V_

`include "sync_signal_mod.v"


module spi_slave #(
	parameter WORDSIZE		= 8,		/* Size of SPI word. Can be anything from 1 to 32. */
	parameter CPOL			= 0,		/* SPI clock polarity. Can be 0 or 1. */
	parameter CPHA			= 0,		/* SPI clock phase. Can be 0 or 1. */
	parameter MSB_FIRST		= 1,		/* MSB transmit first enable. Can be 0 or 1. */
) (
	input clk,							/* clock */
	input mosi,							/* SPI bus MOSI signal */
	output miso,						/* SPI bus MISO signal */
	input sck,							/* SPI bus clock signal */
	input ss,							/* SPI bus slave select signal */
	output rx_irq,						/* Receive interrupt */
	output [WORDSIZE - 1 : 0] rx_data,	/* Received data */
	input [WORDSIZE - 1 : 0] tx_data,	/* Transmit data */
);
	/* Synchronized input signals. */
	wire mosi_s;
	wire sck_rising_s;
	wire sck_falling_s;
	wire ss_s;
	sync_signal sync_mosi(.clk(clk), .in(mosi), .out(mosi_s));
	sync_signal sync_sck(.clk(clk), .in(sck), .rising(sck_rising_s), .falling(sck_falling_s));
	sync_signal sync_ss(.clk(clk), .in(ss), .out(ss_s));

	/* SCK sample and setup edges. */
	wire sck_sample_edge;
	wire sck_setup_edge;
	assign sck_sample_edge = (CPOL ^ CPHA) ? sck_falling_s : sck_rising_s;
	assign sck_setup_edge = (CPOL ^ CPHA) ? sck_rising_s : sck_falling_s;

	/* Output buffers. */
	reg miso_r;
	reg rx_irq_r;
	reg [WORDSIZE - 1 : 0] rx_data_r;
	assign miso = miso_r;
	assign rx_irq = rx_irq_r;
	assign rx_data = rx_data_r;

	/* Receive and transmit shift registers. */
	reg [WORDSIZE - 1 : 0] rx_shiftreg;
	reg [WORDSIZE - 1 : 0] tx_shiftreg;
	reg [5:0] bit_count;

	initial begin
		bit_count <= 0;
		rx_shiftreg <= 0;
		tx_shiftreg <= 0;

		miso_r <= 0;

		rx_irq_r <= 0;
		rx_data_r <= 0;
	end

	always @(posedge clk) begin
		/* Check if slave select is not active */
		if (ss_s) begin
			bit_count <= 0;
			rx_shiftreg <= 0;
			tx_shiftreg <= 0;

			miso_r <= 0;
			rx_irq_r <= 0;

		/* Check if slave select is active */
		end else begin

			/* Check if we are at the start of a word. */
			if (bit_count == 0) begin
				if (CPHA) begin
					/* Reload the TX shift register. */
					tx_shiftreg <= tx_data;
					miso_r <= 0;
				end else begin
					/* Reload the TX shift register and
					 * put the first bit onto the bus. */
					if (MSB_FIRST) begin
						tx_shiftreg <= tx_data << 1;
						miso_r <= tx_data[WORDSIZE - 1];
					end else begin
						tx_shiftreg <= tx_data >> 1;
						miso_r <= tx_data[0];
					end
				end
			/* Check if we are at a setup edge of SCK. */
			end else if (sck_setup_edge) begin
				/* Put the next bit onto the bus. */
				if (MSB_FIRST) begin
					miso_r <= tx_shiftreg[WORDSIZE - 1];
					tx_shiftreg <= tx_shiftreg << 1;
				end else begin
					miso_r <= tx_shiftreg[0];
					tx_shiftreg <= tx_shiftreg >> 1;
				end
			end

			/* Check if we are at a sample edge of SCK. */
			if (sck_sample_edge && (bit_count < WORDSIZE)) begin
				/* Get the next bit from the bus. */
				if (MSB_FIRST) begin
					rx_shiftreg <= rx_shiftreg << 1;
					rx_shiftreg[0] <= mosi_s;
				end else begin
					rx_shiftreg <= rx_shiftreg >> 1;
					rx_shiftreg[WORDSIZE - 1] <= mosi_s;
				end
				bit_count <= bit_count + 1;
			end

			/* If we received a full word, trigger the RX interrupt. */
			if (bit_count >= WORDSIZE) begin
				bit_count <= 0;
				rx_data_r <= rx_shiftreg;
				rx_irq_r <= 1;
			end else begin
				rx_irq_r <= 0;
			end
		end
	end
endmodule

`endif /* SPI_SLAVE_MOD_V_ */
