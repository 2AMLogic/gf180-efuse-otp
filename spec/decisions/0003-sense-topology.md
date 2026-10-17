# 0003 — Sense topology

Status: accepted. Date: 2026-10-17.

## Decision

Current comparison of the selected fuse against a reference resistor
(400 Ω nominal, A6) with a clocked comparator. Margin is computed over intact
140–260 Ω (A4) and programmed ≥ 630 Ω (A5).

## Reasoning

Only the 200 Ω and 900 Ω points are documented; ranges around them are
assumptions. A resistor reference tracks resistor corners, unlike a
fixed-current reference.

## Alternatives

Resistor divider into a comparator (fallback); replicated reference column
(stretch).
