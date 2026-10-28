# 0006 — Controller clock rate

Status: **proposed**. Date: 2026-10-28. It takes effect only after the EE and
market key reviews have run as input and the operator has ratified it. Until
then it changes nothing in `spec/efuse-otp.md`, and T1 item 5 (digital) is not
claimed.

## Decision

The controller clock target is **10 MHz (100 ns period)**. 100 MHz (10 ns) is
not a requirement.

Operator ruling, 2026-10-28, option (a) on issue #35. The alternatives were
requiring 100 MHz with a timing-driven RTL or constraint change (b), and
leaving the rate unspecified (c).

## Reasoning

No spec row or earlier record set a controller clock rate (0004 fixes the
interface as synchronous but not its rate). Routed-DEF `klt sta` evidence,
`sta/README.md` and `sim/controller-sta/`:

- 100 ns: setup and hold slack are non-negative at all five library corners.
  Worst setup slack is +88.77 ns, at `ss_125C_3v00`.
- 10 ns: setup fails by 1.23 ns at `ss_125C_3v00` (44 violating endpoints,
  an internal register path). It passes at the other four corners.

The 10 ns result stays on record as **out-of-spec headroom, not a failure**.
No RTL, layout, constraint or clock was changed to produce either result.

## Consequences

- Once ratified, T1 item 5 (digital) cites the existing 100 ns report. No RTL
  or layout change is needed.
- This record does not close the gaps `sta/README.md` already lists. The
  library has no `fs`/`sf` corner and brackets 3.3 V at ±9 %, not ±10 %.
  Decision 0005 is unchanged.
- The 47 output endpoints carry no output delay, so I/O timing is not covered
  by either report.
- The 10 ns request and report remain as evidence. They are not removed or
  edited.
