# 0001 — Array organization

Status: accepted. Date: 2026-10-17.

## Decision

256 bits as 32 rows × 8 columns (target); 8 bits (1 × 8) fallback; 1 kbit
stretch.

## Reasoning

Row/column addressing is exercised with a modest array; the fallback keeps a
testable block if array-level DRC/LVS blocks. Hard to reverse once layout is
tiled.

## Alternatives rejected

Starting at 1 kbit (array DRC/LVS risk before the cell is proven); a single
row only (no column decode).
