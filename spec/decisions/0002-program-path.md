# 0002 — Program path and supply

Status: accepted. Date: 2026-10-17.

## Decision

One 5 V/6 V-oxide NMOS select device per fuse cell. Program supply external,
nominal 5.0 V ±10% (assumption A1). Required current ≥ 10 mA (A2) and pulse
10 µs (A3) are assumptions with no PDK source. Logic and sense stay in the
3.3 V domain.

## Reasoning

The PDK fuse model is labeled 6V/(5V), so the dual gate oxide matters on the
select device. An on-die supply is out of scope for the test vehicle and
needs its own record.

## Revisit

Replace A1–A3 only with a cited source, via a new record.
