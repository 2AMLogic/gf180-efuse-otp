"""Gate: every via2 (38/0) must overlap merged M3 (42/0), per cell.

The gf180mcu deck does not model V2.3c/V2.3d/V2.4b/V2.4c (they are in the DRC
reports' coverage.unmodeled_rules) and metal3.enclosing.via2.1 passes a via2
with no M3 over it, so DRC cannot gate an unlanded via2. This does.

  layout/check_via2_landing.sh [gds]     exit 0 if every cell reports 0
"""
import sys

import klayout.db as kdb

VIA2, M3 = (38, 0), (42, 0)

layout = kdb.Layout()
layout.read(sys.argv[1])
li_v, li_m = layout.layer(*VIA2), layout.layer(*M3)
bad = 0
for cell in layout.each_cell():
    # flat shapes of this cell's whole hierarchy: a child's via2 is judged
    # against all M3 in the cell it is read in
    vias = kdb.Region(cell.begin_shapes_rec(li_v)).merged()
    m3 = kdb.Region(cell.begin_shapes_rec(li_m)).merged()
    n = sum(1 for v in vias.each() if (kdb.Region(v) & m3).is_empty())
    if vias.count():
        print(f"{cell.name}: {n} via2 with no M3 above (of {vias.count()})")
    bad += n
sys.exit(1 if bad else 0)
