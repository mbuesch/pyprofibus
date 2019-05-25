// vim: ts=4 sw=4 noexpandtab
/*
 *   Profibus PHY
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

`ifndef PROFIBUS_PHY_MOD_V_
`define PROFIBUS_PHY_MOD_V_

`include "uart_mod.v"
`include "spi_slave_mod.v"
`include "block_ram_mod.v"


/* Host SPI message format:
 *
 * Data message master to slave:
 *  Byte 0      1     2...
 *     [0xAA] [FLG] [DATA] ...
 *       |      |      |
 *       |      |      |> from 1 up to 255 Profibus telegram bytes
 *       |      |> Flags
 *       |> Start of message magic constant
 *
 * Data message slave to master:
 *  Byte 0      1     2     ...   9      10
 *     [0x55] [FLG] [DATA0] ... [DATA7] [LEN]
 *       |      |      |                  |
 *       |      |      |                  |> Number of DATA bytes
 *       |      |      |> from 1 up to 8 Profibus telegram bytes
 *       |      |> Flags
 *       |> Start of message magic constant
 *
 * Control message:
 *  Byte 0      1     2       3       4       5       6      7
 *     [MAGC] [FLG] [CTRL] [DATA0] [DATA1] [DATA2] [DATA3] [CRC]
 *       |      |     |       |       |       |       |      |
 *       |      |     |       |       |       |       |      |> CRC-8
 *       |      |     |       |       |       |       |> Control data byte 3 (LSB)
 *       |      |     |       |       |       |> Control data byte 2
 *       |      |     |       |       |> Control data byte 1
 *       |      |     |       |> Control data byte 0 (MSB)
 *       |      |     |> Control identifier
 *       |      |> Flags
 *       |> Start of message magic constant.
 *          0xAA if master to slave.
 *          0x55 if slave to master.
 *
 * FLG: bit 7: odd parity of FLG bits 0-6
 * FLG: bit 6: unused (set to 0)
 * FLG: bit 5: unused (set to 0)
 * FLG: bit 4: unused (set to 0)
 * FLG: bit 3: A reset occurred. Get STATUS to see details.
 * FLG: bit 2: New STATUS available
 * FLG: bit 1: Control message
 * FLG: bit 0: Start of telegram
 *
 * CRC polynomial: x^8 + x^2 + x^1 + 1
 *
 * Padding byte: 0x00
 */


module profibus_telegram_length (
	input clk,
	input n_reset,
	input [7:0] in_byte,
	input new_byte,
	output reg length_valid,
	output reg [7:0] length,
	output reg error,
);
	localparam STATE_START	= 0;
	localparam STATE_LE		= 1;
	localparam STATE_LER	= 2;

	localparam SD1			= 8'h10;
	localparam SD2			= 8'h68;
	localparam SD3			= 8'hA2;
	localparam SD4			= 8'hDC;
	localparam SC			= 8'hE5;

	reg [7:0] byte_le;
	reg [1:0] state;

	initial begin
		length_valid <= 0;
		length <= 0;
		error <= 0;
		byte_le <= 0;
		state <= STATE_START;
	end

	always @(posedge clk) begin
		if (n_reset) begin
			case (state)
				STATE_START: begin
					if (new_byte) begin
						if (in_byte == SD1) begin
							length <= 6;
							error <= 0;
							length_valid <= 1;
						end else if (in_byte == SD2) begin
							length <= 0;
							error <= 0;
							length_valid <= 0;
							state <= STATE_LE;
						end else if (in_byte == SD3) begin
							length <= 14;
							error <= 0;
							length_valid <= 1;
						end else if (in_byte == SD4) begin
							length <= 3;
							error <= 0;
							length_valid <= 1;
						end else if (in_byte == SC) begin
							length <= 1;
							error <= 0;
							length_valid <= 1;
						end else begin
							length <= 0;
							error <= 1;
							length_valid <= 0;
						end
					end
				end
				STATE_LE: begin
					if (new_byte) begin
						if (in_byte >= 4 && in_byte <= 249) begin
							byte_le <= in_byte;
							state <= STATE_LER;
						end else begin
							error <= 1;
							length_valid <= 0;
							state <= STATE_START;
						end
					end
				end
				STATE_LER: begin
					if (new_byte) begin
						if (in_byte == byte_le) begin
							length <= byte_le + 6;
							error <= 0;
							length_valid <= 1;
							state <= STATE_START;
						end else begin
							error <= 1;
							length_valid <= 0;
							state <= STATE_START;
						end
					end
				end
				default: begin
					length_valid <= 0;
					length <= 0;
					error <= 0;
					byte_le <= 0;
					state <= STATE_START;
				end
			endcase
		end else begin
			/* Reset */
			length_valid <= 0;
			length <= 0;
			error <= 0;
			byte_le <= 0;
			state <= STATE_START;
		end
	end
endmodule


module profibus_phy #(
	parameter SPI_CPOL		= 0, 		/* SPI clock polarity. Can be 0 or 1. */
	parameter SPI_CPHA		= 0, 		/* SPI clock phase. Can be 0 or 1. */
	parameter SPI_MSB_FIRST	= 1, 		/* MSB transmit first enable. Can be 0 or 1. */
) (
	input clk,							/* clock */
	input n_reset,						/* Not reset */

	/* Host parallel interface: */
	output rx_irq_edge,					/* Received data available (edge trigger) */
	output rx_irq_level,				/* Received data available (level trigger) */

	/* Host SPI bus interface: */
	input mosi,							/* SPI bus MOSI signal */
	output miso,						/* SPI bus MISO signal */
	input sck,							/* SPI bus clock signal */
	input ss,							/* SPI bus slave select signal */

	/* Profibus RS485 bus: */
	input rx,							/* Raw receive signal line */
	output rx_active,					/* PB receive in progress (optional) */
	output rx_error,					/* PB receive error (optional) */
	output tx,							/* Raw transmit signal line */
	output tx_active,					/* PB transmit in progress (optional) */
	output tx_error,					/* PB transmit error (optional) */

`ifdef DEBUG
	/* Debug interface: */
	output reg debug,
`endif
);
	`include "parity_func.v"
	`include "crc8_func.v"

	localparam TXBUF_ADDR_BITS	= 8;
	localparam RXBUF_ADDR_BITS	= 8;

	/* Start of SPI message magic constant. */
	localparam SPI_MS_MAGIC		= 8'hAA; /* Master to slave */
	localparam SPI_SM_MAGIC		= 8'h55; /* Slave to master */

	/* SPI message FLG bits */
	localparam SPI_FLG_START	= 0;
	localparam SPI_FLG_CTRL		= 1;
	localparam SPI_FLG_NEWSTAT	= 2;
	localparam SPI_FLG_RESET	= 3;
	localparam SPI_FLG_UNUSED4	= 4;
	localparam SPI_FLG_UNUSED5	= 5;
	localparam SPI_FLG_UNUSED6	= 6;
	localparam SPI_FLG_PARITY	= 7;

	/* SPI control message IDs. */
	localparam SPICTRL_NOP			= 0;
	localparam SPICTRL_PING			= 1;
	localparam SPICTRL_PONG			= 2;
	localparam SPICTRL_SOFTRESET	= 3;
	localparam SPICTRL_GETSTATUS	= 4;
	localparam SPICTRL_STATUS		= 5;
	localparam SPICTRL_GETBAUD		= 6;
	localparam SPICTRL_BAUD			= 7;

	/* Status message data bits */
	localparam SPISTAT_PONRESET		= 0;
	localparam SPISTAT_HARDRESET	= 1;
	localparam SPISTAT_SOFTRESET	= 2;
	localparam SPISTAT_TXOVR		= 3;
	localparam SPISTAT_RXOVR		= 4;
	localparam SPISTAT_CTRLCRCERR	= 5;


	/***********************************************************/
	/* General part                                            */
	/***********************************************************/

	/* Power-on-reset, hard-reset and soft-reset status. */
	reg n_poweronreset_status;
	reg n_hardreset_status;
	reg softreset_status;
	/* Soft-reset trigger. */
	reg softreset;

	wire any_reset_status;
	assign any_reset_status = ~n_poweronreset_status | ~n_hardreset_status | softreset_status;

	/* SPICTRL_STATUS should be fetched, if 1. */
	wire new_status_available;
	assign new_status_available = any_reset_status | tx_buf_overflow_get() |
								  rx_buf_overflow_get() | spirx_ctrl_crcerr_get();

	initial begin
		n_poweronreset_status <= 0;
		n_hardreset_status <= 0;
		softreset_status <= 0;
		softreset <= 0;
	end


	/***********************************************************/
	/* Data buffer: Profibus transmit buffer                   */
	/***********************************************************/

	reg [TXBUF_ADDR_BITS - 1 : 0] tx_buf_wr_addr;
	wire [TXBUF_ADDR_BITS - 1 : 0] tx_buf_wr_addr_next;
	reg [7:0] tx_buf_wr_data;
	reg tx_buf_wr;
	reg [TXBUF_ADDR_BITS - 1 : 0] tx_buf_rd_addr;
	wire [7:0] tx_buf_rd_data;
	reg [1:0] tx_buf_overflow;
	block_ram #(
		.ADDR_WIDTH(TXBUF_ADDR_BITS),
		.DATA_WIDTH(8),
		.MEM_BYTES(1 << TXBUF_ADDR_BITS),
	) tx_buf (
		.clk(clk),
		.addr0(tx_buf_wr_addr),
		.wr_data0(tx_buf_wr_data),
		.wr0(tx_buf_wr),
		.addr1(tx_buf_rd_addr),
		.rd_data1(tx_buf_rd_data),
	);
	assign tx_buf_wr_addr_next = tx_buf_wr_addr + 1;

	initial begin
		tx_buf_wr_addr <= 0;
		tx_buf_wr_data <= 0;
		tx_buf_wr <= 0;
		tx_buf_rd_addr <= 0;
		tx_buf_overflow <= 0;
	end

	function automatic tx_buf_overflow_get;
		begin tx_buf_overflow_get = tx_buf_overflow[0] ^ tx_buf_overflow[1]; end
	endfunction

	task automatic tx_buf_overflow_set;
		begin tx_buf_overflow[0] <= ~tx_buf_overflow[1]; end
	endtask

	task automatic tx_buf_overflow_reset;
		begin tx_buf_overflow[1] <= tx_buf_overflow[0]; end
	endtask


	/***********************************************************/
	/* Data buffer: Profibus receive buffer                    */
	/***********************************************************/

	localparam RXBUF_SOT_BIT = 8; /* Start-of-telegram marker bit. */

	reg [RXBUF_ADDR_BITS - 1 : 0] rx_buf_wr_addr;
	wire [RXBUF_ADDR_BITS - 1 : 0] rx_buf_wr_addr_next;
	reg [8:0] rx_buf_wr_data;
	reg rx_buf_wr;
	reg [RXBUF_ADDR_BITS - 1 : 0] rx_buf_rd_addr;
	wire [8:0] rx_buf_rd_data;
	reg [1:0] rx_buf_overflow;
	block_ram #(
		.ADDR_WIDTH(RXBUF_ADDR_BITS),
		.DATA_WIDTH(9),
		.MEM_BYTES(1 << RXBUF_ADDR_BITS),
	) rx_buf (
		.clk(clk),
		.addr0(rx_buf_wr_addr),
		.wr_data0(rx_buf_wr_data),
		.wr0(rx_buf_wr),
		.addr1(rx_buf_rd_addr),
		.rd_data1(rx_buf_rd_data),
	);
	assign rx_buf_wr_addr_next = rx_buf_wr_addr + 1;

	initial begin
		rx_buf_wr_addr <= 0;
		rx_buf_wr_data <= 0;
		rx_buf_wr <= 0;
		rx_buf_rd_addr <= 0;
		rx_buf_overflow <= 0;
	end

	function automatic rx_buf_overflow_get;
		begin rx_buf_overflow_get = rx_buf_overflow[0] ^ rx_buf_overflow[1]; end
	endfunction

	task automatic rx_buf_overflow_set;
		begin rx_buf_overflow[0] <= ~rx_buf_overflow[1]; end
	endtask

	task automatic rx_buf_overflow_reset;
		begin rx_buf_overflow[1] <= rx_buf_overflow[0]; end
	endtask


	/***********************************************************/
	/* UART module                                             */
	/***********************************************************/

	wire uart_rx_irq;
	wire [7:0] uart_rx_data;
	wire uart_rx_parity_ok;
	wire uart_rx_frame_error;
	wire uart_rx_active;
	wire uart_tx_irq;
	wire uart_tx_active;
	wire uart_tx_pending;
	reg [7:0] uart_tx_data;
	reg uart_tx_trigger;
	reg [23:0] uart_clks_per_sym;

	uart_half_duplex #(
		.DATABITS(8),
		.PARITY_EVEN(1),
		.STOP(1),
		.ACTIVE_LOW(0),
	) uart (
		.clk(clk),
		.n_reset(n_reset),
		.clks_per_sym(uart_clks_per_sym),
		.rx(rx),
		.rx_irq(uart_rx_irq),
		.rx_active(uart_rx_active),
		.rx_data(uart_rx_data),
		.rx_parity_ok(uart_rx_parity_ok),
		.rx_frame_error(uart_rx_frame_error),
		.tx(tx),
		.tx_irq(uart_tx_irq),
		.tx_active(uart_tx_active),
		.tx_pending(uart_tx_pending),
		.tx_data(uart_tx_data),
		.tx_trigger(uart_tx_trigger),
	);

	assign rx_active = uart_rx_active;
	assign rx_error = ~uart_rx_parity_ok | uart_rx_frame_error;
	assign tx_active = uart_tx_active;
	assign tx_error = spirx_lencalc_error;

	initial begin
		uart_tx_data <= 0;
		uart_tx_trigger <= 0;
		uart_clks_per_sym <= 0;
	end


	/***********************************************************/
	/* SPI module                                              */
	/***********************************************************/

	wire spi_rx_irq;
	wire spi_tx_irq;
	wire [7:0] spi_rx_data;
	reg [7:0] spi_tx_data;
	spi_slave #(
		.WORDSIZE(8),
		.CPOL(SPI_CPOL),
		.CPHA(SPI_CPHA),
		.MSB_FIRST(SPI_MSB_FIRST),
	) spi (
		.clk(clk),
		.mosi(mosi),
		.miso(miso),
		.sck(sck),
		.ss(ss),
		.rx_irq(spi_rx_irq),
		.rx_data(spi_rx_data),
		.tx_data(spi_tx_data),
	);
	assign spi_tx_irq = spi_rx_irq;

	initial begin
		spi_tx_data <= 0;
	end


	/***********************************************************/
	/* UART receive                                            */
	/* This process receives data from the Profibus line       */
	/* and puts it into the Profibus receive buffer.           */
	/***********************************************************/

	reg [23:0] tsyn_clks;

	/* Receive interrupts */
	assign rx_irq_edge = rx_buf_wr;
	assign rx_irq_level = rx_buf_wr | (rx_buf_wr_addr != rx_buf_rd_addr);

	initial begin
		tsyn_clks <= 0;
	end

	always @(posedge clk) begin
		if (n_reset & ~softreset) begin
			if (uart_rx_irq) begin
				if (uart_rx_parity_ok & ~uart_rx_frame_error) begin
					if (rx_buf_wr_addr_next != rx_buf_rd_addr) begin
						rx_buf_wr_data[7:0] <= uart_rx_data;
						/* Start-of-telegram bit. */
						rx_buf_wr_data[RXBUF_SOT_BIT] <= (timer_idle_saved >= tsyn_clks);
						rx_buf_wr <= 1;
					end else begin
						/* RX buffer overflow. */
						rx_buf_overflow_set();
					end
				end
			end else begin
				if (rx_buf_wr) begin
					rx_buf_wr <= 0;
					rx_buf_wr_addr <= rx_buf_wr_addr_next;
				end
			end
		end else begin
			/* Reset */
			rx_buf_wr <= 0;
			rx_buf_wr_addr <= 0;
		end
	end


	/***********************************************************/
	/* UART transmit.                                          */
	/* This process transmits data to the Profibus line        */
	/* from the Profibus transmit buffer.                      */
	/***********************************************************/

	always @(posedge clk) begin
		if (n_reset & ~softreset) begin
			if (uart_tx_trigger) begin
				uart_tx_trigger <= 0;
			end else begin
				/* Check if new TX data is pending. */
				if (tx_buf_rd_addr != tx_buf_wr_addr) begin
					/* Check if we are able to transmit. */
					if (~uart_tx_active & ~uart_tx_pending) begin
						/* Transmit the byte to the PB line. */
						uart_tx_data <= tx_buf_rd_data;
						uart_tx_trigger <= 1;
						tx_buf_rd_addr <= tx_buf_rd_addr + 1;
					end
				end
			end
		end else begin
			/* Reset */
			uart_tx_data <= 0;
			uart_tx_trigger <= 0;
			tx_buf_rd_addr <= 0;
		end
	end


	/***********************************************************/
	/* SPI receive.                                            */
	/* This process receives data from the host SPI bus        */
	/* and puts it into the Profibus transmit buffer.          */
	/***********************************************************/

	localparam SPIRX_BEGIN		= 0;
	localparam SPIRX_FLG		= 1;
	localparam SPIRX_DATA		= 2;
	localparam SPIRX_CTRL		= 3;
	localparam SPIRX_CTRL_DATA	= 4;
	localparam SPIRX_CRC		= 5;
	localparam SPIRX_CTRL_EXEC	= 6;

	reg [2:0] spirx_state;
	reg [7:0] spirx_len;
	reg spirx_len_valid;
	reg [7:0] spirx_bytecount;
	reg [7:0] spirx_ctrl;
	reg [31:0] spirx_ctrl_data;
	reg [7:0] spirx_crc;
	reg [1:0] spirx_ctrl_crcerr;

	/* Length calculation of PB frames. */
	wire spirx_lencalc_n_reset_wire;
	reg spirx_lencalc_n_reset;
	reg [7:0] spirx_lencalc_byte;
	reg spirx_lencalc_new;
	wire spirx_lencalc_valid;
	wire [7:0] spirx_lencalc_length;
	wire spirx_lencalc_error;
	profibus_telegram_length spirx_lencalc (
		.clk(clk),
		.n_reset(spirx_lencalc_n_reset_wire),
		.in_byte(spirx_lencalc_byte),
		.new_byte(spirx_lencalc_new),
		.length_valid(spirx_lencalc_valid),
		.length(spirx_lencalc_length),
		.error(spirx_lencalc_error),
	);
	assign spirx_lencalc_n_reset_wire = spirx_lencalc_n_reset & ~softreset & n_reset;

	initial begin
		spirx_state <= SPIRX_BEGIN;
		spirx_len <= 0;
		spirx_len_valid <= 0;
		spirx_bytecount <= 0;
		spirx_ctrl <= 0;
		spirx_ctrl_data <= 0;
		spirx_crc <= 0;
		spirx_ctrl_crcerr <= 0;

		spirx_lencalc_n_reset <= 0;
		spirx_lencalc_byte <= 0;
		spirx_lencalc_new <= 0;
	end

	function automatic spirx_ctrl_crcerr_get;
		begin spirx_ctrl_crcerr_get = spirx_ctrl_crcerr[0] ^ spirx_ctrl_crcerr[1]; end
	endfunction

	task automatic spirx_ctrl_crcerr_set;
		begin spirx_ctrl_crcerr[0] <= ~spirx_ctrl_crcerr[1]; end
	endtask

	task automatic spirx_ctrl_crcerr_reset;
		begin spirx_ctrl_crcerr[1] <= spirx_ctrl_crcerr[0]; end
	endtask

	always @(posedge clk) begin
		if (n_reset & ~softreset) begin
			case (spirx_state)
				SPIRX_BEGIN: begin
					/* Wait for start of SPI receive. */
					if (spi_rx_irq) begin
						if (spi_rx_data == SPI_MS_MAGIC) begin
							spirx_ctrl <= 0;
							spirx_ctrl_data <= 0;
							spirx_len <= 0;
							spirx_len_valid <= 0;
							spirx_crc <= 8'hFF;
							spirx_state <= SPIRX_FLG;
						end
					end
					if (tx_buf_wr) begin
						tx_buf_wr_addr <= tx_buf_wr_addr + 1;
						tx_buf_wr <= 0;
					end
					spirx_lencalc_byte <= 0;
					spirx_lencalc_new <= 0;
					spirx_lencalc_n_reset <= 0;
				end
				SPIRX_FLG: begin
					/* Flags field. */
					if (spi_rx_irq) begin
						/* Check the FLG checksum. */
						if (parity8(ODD,
								    spi_rx_data[0],
								    spi_rx_data[1],
								    spi_rx_data[2],
								    spi_rx_data[3],
								    spi_rx_data[4],
								    spi_rx_data[5],
								    spi_rx_data[6],
								    spi_rx_data[7]) == 0) begin
							if (spi_rx_data[SPI_FLG_CTRL]) begin
								/* We have a control message. */
								spirx_bytecount <= 0;
								spirx_state <= SPIRX_CTRL;
							end else begin
								/* Begin PB data. */
								spirx_lencalc_n_reset <= 1;
								spirx_bytecount <= 0;
								spirx_state <= SPIRX_DATA;
							end
						end else begin
							/* Incorrect checksum. */
							spirx_state <= SPIRX_BEGIN;
						end
					end
				end
				SPIRX_DATA: begin
					/* Receive data bytes. */
					if (spirx_len_valid) begin
						/* spirx_len is valid.
						 * Check if we received all bytes. */
						if (spirx_bytecount >= spirx_len) begin
							spirx_state <= SPIRX_BEGIN;
						end
					end else begin
						/* Try to calculate the telegram length. */
						spirx_lencalc_byte <= spi_rx_data;
						spirx_lencalc_new <= spi_rx_irq;
						if (spirx_lencalc_error) begin
							/* Failed to calculate the length. Abort. */
							spirx_lencalc_n_reset <= 0;
							spirx_state <= SPIRX_BEGIN;
						end else if (spirx_lencalc_valid) begin
							/* Successfully calculated the data length. */
							spirx_len <= spirx_lencalc_length;
							spirx_len_valid <= 1;
							spirx_lencalc_n_reset <= 0;
						end
					end
					if (tx_buf_wr) begin
						/* Increment TX buffer pointer. */
						tx_buf_wr_addr <= tx_buf_wr_addr + 1;
						tx_buf_wr <= 0;
					end else begin
						/* Did we receive a byte? */
						if (spi_rx_irq) begin
							if (tx_buf_wr_addr_next != tx_buf_rd_addr) begin
								/* Put the new byte into the TX buffer. */
								tx_buf_wr_data <= spi_rx_data;
								tx_buf_wr <= 1;
								spirx_bytecount <= spirx_bytecount + 1;
							end else begin
								/* TX buffer overflow. */
								tx_buf_overflow_set();
								spirx_bytecount <= spirx_bytecount + 1;
							end
						end
					end
				end
				SPIRX_CTRL: begin
					/* Receive control command byte. */
					if (spi_rx_irq) begin
						spirx_ctrl <= spi_rx_data;
						spirx_crc <= crc8(spirx_crc, spi_rx_data);
						spirx_state <= SPIRX_CTRL_DATA;
					end
				end
				SPIRX_CTRL_DATA: begin
					/* Receive control data bytes. */
					if (spi_rx_irq) begin
						spirx_ctrl_data <= (spirx_ctrl_data << 8) | spi_rx_data;
						spirx_crc <= crc8(spirx_crc, spi_rx_data);
						if (spirx_bytecount >= 4 - 1) begin
							spirx_state <= SPIRX_CRC;
						end
						spirx_bytecount <= spirx_bytecount + 1;
					end
				end
				SPIRX_CRC: begin
					/* Receive CRC byte. */
					if (spi_rx_irq) begin
						if (spi_rx_data == spirx_crc) begin
							spirx_state <= SPIRX_CTRL_EXEC;
						end else begin
							/* Incorrect CRC. Do not run the control command. */
							spirx_ctrl_crcerr_set();
							spirx_state <= SPIRX_BEGIN;
						end
					end
				end
				SPIRX_CTRL_EXEC: begin
					/* Handle received control message. */
					case (spirx_ctrl)
						SPICTRL_NOP: begin
							/* NOP command. Do nothing. */
							spirx_state <= SPIRX_BEGIN;
						end
						SPICTRL_PING: begin
							/* PING command. Send PONG. */
							if (spitx_ctrl_pending == spitx_ctrl_pending_ack) begin
								spitx_ctrl_reply <= SPICTRL_PONG;
								spitx_ctrl_reply_data <= 0;
								spitx_ctrl_pending <= ~spitx_ctrl_pending_ack;

								spirx_state <= SPIRX_BEGIN;
							end
						end
						SPICTRL_PONG: begin
							/* Ignore. */
							spirx_state <= SPIRX_BEGIN;
						end
						SPICTRL_SOFTRESET: begin
							/* Trigger a soft reset. */
							softreset <= 1;
							spirx_state <= SPIRX_BEGIN;
						end
						SPICTRL_GETSTATUS: begin
							if (spitx_ctrl_pending == spitx_ctrl_pending_ack) begin
								spitx_ctrl_reply <= SPICTRL_STATUS;
								spitx_ctrl_reply_data[SPISTAT_PONRESET] <= ~n_poweronreset_status;
								spitx_ctrl_reply_data[SPISTAT_HARDRESET] <= ~n_hardreset_status;
								spitx_ctrl_reply_data[SPISTAT_SOFTRESET] <= softreset_status;
								spitx_ctrl_reply_data[SPISTAT_TXOVR] <= tx_buf_overflow_get();
								spitx_ctrl_reply_data[SPISTAT_RXOVR] <= rx_buf_overflow_get();
								spitx_ctrl_reply_data[SPISTAT_CTRLCRCERR] <= spirx_ctrl_crcerr_get();
								spitx_ctrl_reply_data[31:6] <= 0;
								spitx_ctrl_pending <= ~spitx_ctrl_pending_ack;

								/* Reset all error states. */
								tx_buf_overflow_reset();
								rx_buf_overflow_reset();
								spirx_ctrl_crcerr_reset();

								/* Reset all reset status bits */
								n_poweronreset_status <= 1;
								n_hardreset_status <= 1;
								softreset_status <= 0;

								spirx_state <= SPIRX_BEGIN;
							end
						end
						SPICTRL_STATUS: begin
							/* Ignore. */
							spirx_state <= SPIRX_BEGIN;
						end
						SPICTRL_GETBAUD: begin
							if (spitx_ctrl_pending == spitx_ctrl_pending_ack) begin
								spitx_ctrl_reply <= SPICTRL_BAUD;
								spitx_ctrl_reply_data[31:24] <= 0;
								spitx_ctrl_reply_data[23:0] <= spirx_ctrl_data[23:0];
								spitx_ctrl_pending <= ~spitx_ctrl_pending_ack;

								spirx_state <= SPIRX_BEGIN;
							end
						end
						SPICTRL_BAUD: begin
							if (spitx_ctrl_pending == spitx_ctrl_pending_ack) begin
								spitx_ctrl_reply <= SPICTRL_BAUD;
								spitx_ctrl_reply_data[31:24] <= 0;
								spitx_ctrl_reply_data[23:0] <= spirx_ctrl_data[23:0];
								spitx_ctrl_pending <= ~spitx_ctrl_pending_ack;

								/* Set the new baud rate. */
								uart_clks_per_sym[23:0] <= spirx_ctrl_data[23:0];

								/* Set the new TSYN timing.
								 * The number of TSYN clks is:
								 * clks_per_symbol * 33
								 */
								tsyn_clks <= (spirx_ctrl_data[23:0] << 5) + spirx_ctrl_data[23:0];

								spirx_state <= SPIRX_BEGIN;
							end
						end
						default: begin
							/* Unknown control command. */
							spirx_state <= SPIRX_BEGIN;
						end
					endcase
				end
				default: begin
					/* Invalid case. */
					spirx_ctrl <= 0;
					spirx_ctrl_data <= 0;
					tx_buf_wr_addr <= 0;
					tx_buf_wr_data <= 0;
					tx_buf_wr <= 0;
					spirx_state <= SPIRX_BEGIN;
					spirx_lencalc_n_reset <= 0;
				end
			endcase
		end else begin
			/* Reset */
			spirx_ctrl <= 0;
			spirx_ctrl_data <= 0;
			tx_buf_wr_addr <= 0;
			tx_buf_wr_data <= 0;
			tx_buf_wr <= 0;
			spirx_state <= SPIRX_BEGIN;
			spirx_lencalc_n_reset <= 0;
			rx_buf_overflow_reset();
			tx_buf_overflow_reset();
			spirx_ctrl_crcerr_reset();

			softreset_status <= softreset;
			n_hardreset_status <= n_reset;
			n_poweronreset_status <= 1;
			softreset <= 0;
		end
	end


	/***********************************************************/
	/* SPI transmit.                                           */
	/* This process transmits data to the host SPI bus         */
	/* from the Profibus receive buffer.                       */
	/***********************************************************/

	reg [7:0] spitx_ctrl_reply;
	reg [31:0] spitx_ctrl_reply_data;
	reg spitx_ctrl_pending;
	reg spitx_ctrl_pending_ack;
	reg [7:0] spitx_bytecount;
	reg [7:0] spitx_len;
	reg spitx_tail;
	reg spitx_ctrl_running;
	reg spitx_data_running;
	reg [7:0] spitx_crc;

	initial begin
		spitx_ctrl_reply <= 0;
		spitx_ctrl_reply_data <= 0;
		spitx_ctrl_pending <= 0;
		spitx_ctrl_pending_ack <= 0;
		spitx_bytecount <= 0;
		spitx_len <= 0;
		spitx_ctrl_running <= 0;
		spitx_data_running <= 0;
		spitx_crc <= 0;
	end

	always @(posedge clk) begin
		if (n_reset & ~softreset) begin
			/* Are we currently not transmitting a data frame
			 * and is a control frame pending? */
			if (~spitx_data_running &&
			    spitx_ctrl_pending != spitx_ctrl_pending_ack) begin
				if (spi_tx_irq) begin
					case (spitx_bytecount)
						0: begin
							spi_tx_data <= SPI_SM_MAGIC;
							spitx_bytecount <= spitx_bytecount + 1;
							spitx_ctrl_running <= 1;
						end
						1: begin
							spi_tx_data[SPI_FLG_START] <= 0;
							spi_tx_data[SPI_FLG_CTRL] <= 1;
							spi_tx_data[SPI_FLG_NEWSTAT] <= new_status_available;
							spi_tx_data[SPI_FLG_RESET] <= any_reset_status;
							spi_tx_data[SPI_FLG_UNUSED4] <= 0;
							spi_tx_data[SPI_FLG_UNUSED5] <= 0;
							spi_tx_data[SPI_FLG_UNUSED6] <= 0;
							spi_tx_data[SPI_FLG_PARITY] <= parity8(ODD, 0,
											0,
											1,
											new_status_available,
											any_reset_status,
											0,
											0,
											0);
							spitx_crc <= 8'hFF;
							spitx_bytecount <= spitx_bytecount + 1;
							spitx_ctrl_running <= 1;
						end
						2: begin
							spi_tx_data <= spitx_ctrl_reply;
							spitx_crc <= crc8(spitx_crc, spitx_ctrl_reply);
							spitx_bytecount <= spitx_bytecount + 1;
							spitx_ctrl_running <= 1;
						end
						3: begin
							spi_tx_data <= spitx_ctrl_reply_data[31:24];
							spitx_crc <= crc8(spitx_crc, spitx_ctrl_reply_data[31:24]);
							spitx_bytecount <= spitx_bytecount + 1;
							spitx_ctrl_running <= 1;
						end
						4: begin
							spi_tx_data <= spitx_ctrl_reply_data[23:16];
							spitx_crc <= crc8(spitx_crc, spitx_ctrl_reply_data[23:16]);
							spitx_bytecount <= spitx_bytecount + 1;
							spitx_ctrl_running <= 1;
						end
						5: begin
							spi_tx_data <= spitx_ctrl_reply_data[15:8];
							spitx_crc <= crc8(spitx_crc, spitx_ctrl_reply_data[15:8]);
							spitx_bytecount <= spitx_bytecount + 1;
							spitx_ctrl_running <= 1;
						end
						6: begin
							spi_tx_data <= spitx_ctrl_reply_data[7:0];
							spitx_crc <= crc8(spitx_crc, spitx_ctrl_reply_data[7:0]);
							spitx_bytecount <= spitx_bytecount + 1;
							spitx_ctrl_running <= 1;
						end
						7: begin
							spi_tx_data <= spitx_crc;
							spitx_bytecount <= 0;
							spitx_ctrl_running <= 0;
							spitx_ctrl_pending_ack <= spitx_ctrl_pending;
						end
						default: begin
							spitx_bytecount <= 0;
							spitx_ctrl_running <= 0;
							spitx_ctrl_pending_ack <= spitx_ctrl_pending;
						end
					endcase
				end
			/* Are we currently not transmitting a control frame
			 * and is a data frame pending? */
			end else if ((~spitx_ctrl_running &&
			              rx_buf_wr_addr != rx_buf_rd_addr) ||
						 spitx_data_running) begin
				if (spi_tx_irq) begin
					/* We have a new PB telegram byte. Send it to the host. */
					if (spitx_bytecount == 0) begin
						spi_tx_data <= SPI_SM_MAGIC;
						spitx_bytecount <= spitx_bytecount + 1;
						spitx_len <= 0;
						spitx_tail <= 0;
						spitx_data_running <= 1;
					end else if (spitx_bytecount == 1) begin
						spi_tx_data[SPI_FLG_START] = rx_buf_rd_data[RXBUF_SOT_BIT];
						spi_tx_data[SPI_FLG_CTRL] = 0;
						spi_tx_data[SPI_FLG_NEWSTAT] = new_status_available;
						spi_tx_data[SPI_FLG_RESET] = any_reset_status;
						spi_tx_data[SPI_FLG_UNUSED4] = 0;
						spi_tx_data[SPI_FLG_UNUSED5] = 0;
						spi_tx_data[SPI_FLG_UNUSED6] = 0;
						spi_tx_data[SPI_FLG_PARITY] = parity8(ODD, 0,
										rx_buf_rd_data[RXBUF_SOT_BIT],
										0,
										new_status_available,
										any_reset_status,
										0,
										0,
										0);
						spitx_bytecount <= spitx_bytecount + 1;
						spitx_data_running <= 1;
					end else if (spitx_bytecount >= 2 && spitx_bytecount <= 9) begin
						if (spitx_tail ||
						    (rx_buf_wr_addr == rx_buf_rd_addr) ||
						    (spitx_bytecount >= 3 && rx_buf_rd_data[RXBUF_SOT_BIT])) begin
							spi_tx_data <= 0;
							spitx_bytecount <= spitx_bytecount + 1;
							spitx_tail <= 1;
						end else begin
							spi_tx_data <= rx_buf_rd_data;
							rx_buf_rd_addr <= rx_buf_rd_addr + 1;
							spitx_bytecount <= spitx_bytecount + 1;
							spitx_len <= spitx_len + 1;
						end
						spitx_data_running <= 1;
					end else begin
						spi_tx_data <= spitx_len;
						spitx_bytecount <= 0;
						spitx_data_running <= 0;
					end
				end
			end else begin
				/* No frame pending. */
				if (spi_tx_irq) begin
					spi_tx_data <= 0;
				end
				spitx_bytecount <= 0;
				spitx_data_running <= 0;
				spitx_ctrl_running <= 0;
			end
		end else begin
			/* Reset. */
			spi_tx_data <= 0;
			spitx_bytecount <= 0;
			spitx_len <= 0;
			spitx_tail <= 0;
			spitx_ctrl_running <= 0;
			spitx_data_running <= 0;
			spitx_ctrl_pending_ack <= spitx_ctrl_pending;
			spitx_crc <= 0;
		end
	end


	/***********************************************************/
	/* PB timekeeping.                                         */
	/***********************************************************/

	reg timer_idle_active;
	reg [23:0] timer_idle;
	reg [23:0] timer_idle_saved;
	localparam TIMER_MAX = 24'hFFFFFF;

	initial begin
		timer_idle_active <= 0;
		timer_idle <= 0;
		timer_idle_saved <= TIMER_MAX;
	end

	always @(posedge clk) begin
		if (n_reset & ~softreset) begin
			if (uart_tx_active | uart_tx_irq |
			    uart_rx_active | uart_rx_irq) begin
				/* A PB transmission is active. Reset idle timer. */
				if (timer_idle_active) begin
					timer_idle_saved <= timer_idle;
				end
				timer_idle_active <= 0;
				timer_idle <= 0;
			end else begin
				/* PB is idle, increment the idle timer. Avoid overflow. */
				if (timer_idle < TIMER_MAX) begin
					timer_idle <= timer_idle + 1;
				end
				timer_idle_active <= 1;
			end
		end else begin
			timer_idle_active <= 0;
			timer_idle <= 0;
			timer_idle_saved <= TIMER_MAX;
		end
	end

endmodule


`endif /* PROFIBUS_PHY_MOD_V_ */
