# 0004 — Controller interface and power-up protection

Status: accepted. Date: 2026-10-17.

## Decision

Synchronous interface (clock, address, program-enable, read-enable, data,
busy). Program-enable is ignored until a registered arm state is set after
reset release; program outputs are held inactive during reset and power-up.
Asynchronous parallel read is the fallback; serial is the stretch.

## Reasoning

An unintended program pulse is irreversible, so the safe state is the reset
state and arming is explicit.
