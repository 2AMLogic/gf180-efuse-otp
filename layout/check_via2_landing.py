"""Gate: every via2 (38/0) must overlap merged M3 (42/0) above AND merged M2
(36/0) below, per cell.

The gf180mcu deck does not model V2.3c/V2.3d/V2.4b/V2.4c (they are in the DRC
reports' coverage.unmodeled_rules) and metal3.enclosing.via2.1 /
metal2.enclosing.via2.1 pass a via2 with no M3 / no M2 under it, and LVS
cannot see a dead cut, so DRC and LVS cannot gate an unlanded via2. This does,
on both sides: a one-sided gate missed 16 cuts with no M2 below.

A cell's via2 is judged against the M2/M3 visible in that cell's whole
hierarchy, so a child via2 landed only by a parent's metal would read as bad
in the child; every cell reads 0 today.

  layout/check_via2_landing.sh [gds]     exit 0 if every cell reports 0
"""
import sys

import klayout.db as kdb

VIA2, M2, M3 = (38, 0), (36, 0), (42, 0)

layout = kdb.Layout()
layout.read(sys.argv[1])
li_v, li_2, li_3 = layout.layer(*VIA2), layout.layer(*M2), layout.layer(*M3)
bad = 0
for cell in layout.each_cell():
    # flat shapes of this cell's whole hierarchy
    vias = kdb.Region(cell.begin_shapes_rec(li_v)).merged()
    if not vias.count():
        continue
    m2 = kdb.Region(cell.begin_shapes_rec(li_2)).merged()
    m3 = kdb.Region(cell.begin_shapes_rec(li_3)).merged()
    no_m3 = sum(1 for v in vias.each() if (kdb.Region(v) & m3).is_empty())
    no_m2 = sum(1 for v in vias.each() if (kdb.Region(v) & m2).is_empty())
    print(f"{cell.name}: {no_m3} via2 with no M3 above, "
          f"{no_m2} with no M2 below (of {vias.count()})")
    bad += no_m3 + no_m2
sys.exit(1 if bad else 0)
