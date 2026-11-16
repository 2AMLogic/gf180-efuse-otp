// Deliberate negative control for the latch gate — NOT design RTL, and never
// part of efuse_otp_ctrl. rtl/synth.sh --negative-control synthesizes this
// file through rtl/synth-negctl.ys and passes only if the asserted pattern set
// in rtl/latch-assert.ys fires on it. The level-sensitive always block infers
// a latch on q; q is an output port, so opt_clean cannot remove it and the
// latch survives synthesis (an unobservable latch would be optimized away and
// make the control pass vacuously).
module latch_negative_control (
  input  wire en,
  input  wire d,
  output reg  q
);
  always @(*) if (en) q = d;
endmodule
