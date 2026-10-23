// efuse_otp_ctrl -- synchronous controller for the eFuse OTP array.
//
// Spec: spec/efuse-otp.md section 2 ("Controller interface", "Controller
// behavior"), decision record spec/decisions/0004-interface-and-protection.md.
// Interface details and the arming choice are in rtl/README.md.
//
// Verilog-2001, one clock, one synchronous reset, no latches, no gated clocks.
//
// Protection (0004): an unintended program pulse is irreversible, so
//   * every program-side output (prog_strobe, row_sel, col_sel) is a register
//     ANDed with ~rst, so it is inactive the moment rst is asserted and
//     before any clock edge (power-up included);
//   * program requests are ignored until the registered `armed` bit is set,
//     which happens on the second clock edge after rst deasserts;
//   * a request needs a rising edge of prog_en, so an enable stuck high from
//     reset or power-up never programs anything.
module efuse_otp_ctrl #(
    parameter ROWS          = 32,        // array rows
    parameter COLS          = 8,         // array columns
    parameter AW            = 8,         // address bits = clog2(ROWS*COLS)
    parameter CLK_HZ        = 10000000,  // clock frequency
    parameter PULSE_US      = 10,        // program pulse width, clamped to 1..100 us (A3)
    parameter SETTLE_CYCLES = 4          // sense-settle count, clamped to >= 1
) (
    input               clk,
    input               rst,            // active high, synchronous
    input  [AW-1:0]     addr,           // bit address = row*COLS + col
    input               prog_en,        // rising edge requests a program pulse
    input               rd_en,          // rising edge requests a read
    input               sense_in,       // clocked comparator output, 1 = programmed
    output              prog_strobe,    // program drive, one pulse per request
    output [ROWS-1:0]   row_sel,        // one-hot row select, latched address
    output [COLS-1:0]   col_sel,        // one-hot column select, latched address
    output              sense_en,       // sense path enabled during settle
    output reg          dout,           // last sampled sense_in
    output              busy            // high from the cycle after acceptance until done
);

    // ---- elaboration-time constants (constant functions, Verilog-2001) ----
    function integer clog2;
        input integer v;
        integer i;
        begin
            clog2 = 0;
            for (i = 1; i < v; i = i * 2)
                clog2 = clog2 + 1;
        end
    endfunction

    // round(PULSE_US * CLK_HZ / 1e6) in 64 bits (100 us * 100 MHz overflows 32).
    function integer pulse_cycles;
        input integer us;
        input integer hz;
        reg [63:0] t;
        integer u;
        begin
            u = us;
            if (u < 1)   u = 1;
            if (u > 100) u = 100;
            t = u;
            t = t * hz;
            t = (t + 500000) / 1000000;
            pulse_cycles = t;
            if (pulse_cycles < 1) pulse_cycles = 1;
        end
    endfunction

    localparam PULSE_N  = pulse_cycles(PULSE_US, CLK_HZ);
    localparam SETTLE_N = (SETTLE_CYCLES < 1) ? 1 : SETTLE_CYCLES;
    localparam CW       = clog2(((PULSE_N > SETTLE_N) ? PULSE_N : SETTLE_N) + 1);

    localparam [1:0] S_IDLE   = 2'd0,
                     S_SEL    = 2'd1,   // program: selects up, strobe still low
                     S_PULSE  = 2'd2,   // program: strobe high for PULSE_N cycles
                     S_SETTLE = 2'd3;   // read: sense_en high for SETTLE_N cycles

    reg [1:0]      state;
    reg            released;            // set on the first edge with rst low
    reg            armed;               // set on the second edge with rst low
    reg            prog_prev, rd_prev;  // for rising-edge request detection
    reg [CW-1:0]   cnt;
    reg [ROWS-1:0] row_q;
    reg [COLS-1:0] col_q;
    reg            prog_q, sense_q;

    wire prog_rise = prog_en & ~prog_prev;
    wire rd_rise   = rd_en & ~rd_prev;
    wire addr_ok   = (addr < ROWS * COLS);

    // One-hot decode of the incoming address (used only on the accepting edge).
    reg [ROWS-1:0] row_n;
    reg [COLS-1:0] col_n;
    integer k;
    always @* begin
        for (k = 0; k < ROWS; k = k + 1) row_n[k] = ((addr / COLS) == k);
        for (k = 0; k < COLS; k = k + 1) col_n[k] = ((addr % COLS) == k);
    end

    always @(posedge clk) begin
        if (rst) begin
            state     <= S_IDLE;
            released  <= 1'b0;
            armed     <= 1'b0;
            prog_prev <= 1'b1;          // an enable held high through reset needs a fresh edge
            rd_prev   <= 1'b1;
            cnt       <= {CW{1'b0}};
            row_q     <= {ROWS{1'b0}};
            col_q     <= {COLS{1'b0}};
            prog_q    <= 1'b0;
            sense_q   <= 1'b0;
            dout      <= 1'b0;
        end else begin
            prog_prev <= prog_en;
            rd_prev   <= rd_en;
            released  <= 1'b1;
            armed     <= released;

            case (state)
                S_IDLE: begin
                    // Read has priority over program when both rise together
                    // (a read is harmless, a program is irreversible).
                    if (rd_rise) begin
                        if (addr_ok) begin
                            row_q   <= row_n;
                            col_q   <= col_n;
                            sense_q <= 1'b1;
                            cnt     <= SETTLE_N - 1;
                            state   <= S_SETTLE;
                        end
                    end else if (prog_rise && armed && addr_ok) begin
                        row_q <= row_n;
                        col_q <= col_n;
                        state <= S_SEL;
                    end
                end
                S_SEL: begin
                    prog_q <= 1'b1;
                    cnt    <= PULSE_N - 1;
                    state  <= S_PULSE;
                end
                S_PULSE: begin
                    if (cnt == 0) begin
                        prog_q <= 1'b0;
                        row_q  <= {ROWS{1'b0}};
                        col_q  <= {COLS{1'b0}};
                        state  <= S_IDLE;
                    end else begin
                        cnt <= cnt - 1'b1;
                    end
                end
                S_SETTLE: begin
                    if (cnt == 0) begin
                        dout    <= sense_in;
                        sense_q <= 1'b0;
                        row_q   <= {ROWS{1'b0}};
                        col_q   <= {COLS{1'b0}};
                        state   <= S_IDLE;
                    end else begin
                        cnt <= cnt - 1'b1;
                    end
                end
            endcase
        end
    end

    // Outputs are registers gated by ~rst: inactive immediately in reset.
    assign prog_strobe = prog_q  & ~rst;
    assign row_sel     = row_q   & {ROWS{~rst}};
    assign col_sel     = col_q   & {COLS{~rst}};
    assign sense_en    = sense_q & ~rst;
    assign busy        = (state != S_IDLE) & ~rst;

endmodule
