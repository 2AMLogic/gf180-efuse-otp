#!/usr/bin/env python3
"""efuse_ls routing: the two-row floorplan and drawn M1-M3 routing.

ls_cell and its signal, supply and label helpers, plus the M2 landing-pad and
M3 strip primitives they draw with (see layout/README.md, "efuse_ls
routing"). efuse_rowdrv and efuse_coldrv (route_drivers.py) reuse _ls_vstrip
for their own M3 lanes; efuse_otp_array's top routing (route_array.py) taps
the vss rail at LS_VSS_RAIL_Y.
"""

from analog_core import (LS_M2, LS_M3, LS_VIA1, LS_VIA2, LS_PAD2, LS_VIA_SIZE,
                         LS_W2, LS_W3, LS_W3N, gs)

# efuse_ls routing (see ls_cell and layout/README.md, "efuse_ls routing").
LS_V2_END = LS_VIA_SIZE / 2 + 0.06  # M3 end that lands a via2 reaches this far past the cut centre: on M3 narrower than 0.34 um the cut needs 0.06 um of end overlap (V2.4b) and, its side overlap below 0.04 um, 0.06 um on the adjacent edges too (V2.4c)
# Stated floorplan, um: bbox lower-left of each leaf, two device rows.
LS_COL_X = {"XMpi": 0.0, "XMni": 0.0, "XMp1": 6.24, "XMn1": 6.24,
            "XMp2": 12.90, "XMn2": 12.90}
LS_ROW_Y = {"XMpi": 12.0, "XMp1": 12.0, "XMp2": 12.0,
            "XMni": 0.0, "XMn1": 0.0, "XMn2": 0.0}
LS_NMOS = ("XMni", "XMn1", "XMn2")
LS_VSS_RAIL_Y = -1.5  # M2 rail below the NMOS row
LS_TRACK_Y = {"in": 8.6, "inb": 10.2, "out": 11.0}
LS_JUNC_X = {"inb": 5.0, "x1": 11.5, "out": 12.3}  # channel-area junctions
LS_M3_HORIZ_Y = {"x1": 17.2, "out": 18.0}  # runs above the PMOS row


def ls_cell(b, subckt):
    """efuse_ls on a stated two-row floorplan, with drawn routing.

    Floorplan (um, this cell's own coordinates): NMOS row at y=0
    (XMni x=0, XMn1 x=6.24, XMn2 x=12.90), PMOS row at y=12.0 (XMpi,
    XMp1, XMp2 at the same three column origins) -- the input inverter
    in column 0, the two cross-coupled 6 V inverters in columns 1 and 2,
    so the 3.3 V pair and the 6 V quad each stay in one row and each
    column keeps a device's source, drain and gate pads vertically
    aligned. Routing: M1 device pads and guard-ring taps; M2 horizontal
    (supply rails, per-net channel runs); M3 vertical (per-pad stubs);
    0.26 um via1/via2 cuts on 0.4 um M2 landing pads. Every source pad
    is merged into its own guard ring with an M1 bridge (source and body
    are one net on each device), and each ring leaves the island at one
    tap: TAP_S for the NMOS row and the 6 V PMOS pair (both to wires in
    the channel or below it), TAP_W for XMpi (vdd33 exits west).
    """
    insts = {i["name"]: i for i in b.netlist[subckt]}
    expected = {"XMpi", "XMni", "XMn1", "XMn2", "XMp1", "XMp2"}
    assert set(insts) == expected, f"efuse_ls netlist changed: {sorted(insts)}"
    cell = b.layout.create_cell(subckt)
    ports = {}
    for iname, inst in insts.items():
        child = b.leaf(subckt, inst)
        rep = b.reports[f"{subckt}__{iname[1:]}"]
        col, row = LS_COL_X[iname], LS_ROW_Y[iname]
        dx, dy = b.place(cell, child, col, row)
        ports[iname] = {p["name"]: (gs(dx + p["x_um"]), gs(dy + p["y_um"]),
                                    p["width_um"], p["direction_deg"])
                        for p in rep["ports"]}
    # Create the routing layers before any shape is drawn, in the order
    # the committed GDS was first written with: klayout emits each cell's
    # shapes in layer-index order, and a layer's index is fixed by the
    # first draw that touches it, so without this the stream bytes would
    # depend on which helper happens to draw first (same geometry,
    # different file).
    for pair in (LS_M2, LS_VIA1, LS_M3, LS_VIA2):
        b.layout.layer(*pair)
    _ls_supplies(b, cell, ports)
    _ls_signals(b, cell, ports)
    _ls_labels(b, cell, ports)
    b.ls_ports = ports
    b.cells[subckt] = cell
    return cell


def _ls_supplies(b, cell, ports):
    rail = LS_VSS_RAIL_Y
    # vss: rail below the NMOS row; one tap stub per NMOS ring.
    b._box(cell, LS_M2, 0.9, rail - LS_W2 / 2, 16.0, rail + LS_W2 / 2)
    for iname in LS_NMOS:
        ts = ports[iname]["TAP_S"]
        b._m1_ring_bridge(cell, ports[iname]["U0_S"], ports[iname]["TAP_W"])
        b._cut(cell, LS_VIA1, ts[0], ts[1])
        b._box(cell, LS_M2, ts[0] - LS_W2 / 2, rail - LS_W2 / 2,
               ts[0] + LS_W2 / 2, ts[1] + LS_W2 / 2)
    # vdd33: XMpi only; TAP_W exits west to a short open-ended stub.
    tw = ports["XMpi"]["TAP_W"]
    b._m1_ring_bridge(cell, ports["XMpi"]["U0_S"], tw)
    b._cut(cell, LS_VIA1, tw[0], tw[1])
    b._box(cell, LS_M2, -1.2, tw[1] - LS_W2 / 2, tw[0] + LS_W2 / 2, tw[1] + LS_W2 / 2)
    # vprog: the 6 V PMOS pair; TAP_S of both rings, joined in the channel top.
    ts1, ts2 = ports["XMp1"]["TAP_S"], ports["XMp2"]["TAP_S"]
    for iname, ts in (("XMp1", ts1), ("XMp2", ts2)):
        b._m1_ring_bridge(cell, ports[iname]["U0_S"], ports[iname]["TAP_W"])
        b._cut(cell, LS_VIA1, ts[0], ts[1])
    b._box(cell, LS_M2, ts1[0] - LS_W2 / 2, ts1[1] - LS_W2 / 2,
           ts2[0] + LS_W2 / 2, ts1[1] + LS_W2 / 2)


def _ls_signals(b, cell, ports):
    ni, pi, n1, p1, n2, p2 = (ports[n] for n in
                              ("XMni", "XMpi", "XMn1", "XMp1", "XMn2", "XMp2"))
    # in: XMni.G <-> XMpi.G straight up column 0; branch west-to-east on
    # M2 to XMn1.G, down a short M3 stub.
    g_ni, g_pi, g_n1 = ni["U0_G"], pi["U0_G"], n1["U0_G"]
    _ls_pad3(b, cell, g_ni)
    _ls_pad3(b, cell, g_pi)
    _ls_vstrip(b, cell, g_ni[0], g_ni[1], g_pi[1], LS_W3)
    y = LS_TRACK_Y["in"]
    b._cut(cell, LS_VIA2, g_ni[0], y)
    b._box(cell, LS_M2, g_ni[0] - LS_W2 / 2, y - LS_W2 / 2, g_n1[0] + LS_W2 / 2, y + LS_W2 / 2)
    _ls_vstrip(b, cell, g_n1[0], g_n1[1], y, LS_W3)
    b._cut(cell, LS_VIA2, g_n1[0], y)
    _ls_pad3(b, cell, g_n1)
    # inb: XMni.D east on M2 at pad height, M3 up the col0/col1 gap to the
    # channel track, east to XMn2.G, down a stub; XMpi.D east on M2 at pad
    # height to the same M3 (the two legs meet the track at one junction).
    d_ni, d_pi, g_n2 = ni["U0_D"], pi["U0_D"], n2["U0_G"]
    jx = LS_JUNC_X["inb"]
    yt = LS_TRACK_Y["inb"]
    _ls_pad3(b, cell, d_ni, via2=False)
    b._box(cell, LS_M2, d_ni[0], d_ni[1] - LS_W2 / 2, jx + LS_W2 / 2, d_ni[1] + LS_W2 / 2)
    _ls_vstrip(b, cell, jx, d_ni[1], d_pi[1], LS_W3)
    b._cut(cell, LS_VIA2, jx, d_ni[1])
    _ls_pad3(b, cell, d_pi, via2=False)
    b._box(cell, LS_M2, d_pi[0], d_pi[1] - LS_W2 / 2, jx + LS_W2 / 2, d_pi[1] + LS_W2 / 2)
    b._cut(cell, LS_VIA2, jx, d_pi[1])
    b._box(cell, LS_M2, jx - LS_W2 / 2, yt - LS_W2 / 2, g_n2[0] + LS_W2 / 2, yt + LS_W2 / 2)
    b._cut(cell, LS_VIA2, jx, yt)
    _ls_vstrip(b, cell, g_n2[0], g_n2[1], yt, LS_W3)
    b._cut(cell, LS_VIA2, g_n2[0], yt)
    _ls_pad3(b, cell, g_n2)
    # x1: XMn1.D east on M2 at pad height, M3 up the col1/col2 gap; XMp1.D
    # taps that M3 through an M2 run at pad height; on top an M3 run east
    # drops into XMp2.G.
    d_n1, d_p1, g_p2 = n1["U0_D"], p1["U0_D"], p2["U0_G"]
    jx = LS_JUNC_X["x1"]
    yh = LS_M3_HORIZ_Y["x1"]
    _ls_pad3(b, cell, d_n1, via2=False)
    b._box(cell, LS_M2, d_n1[0], d_n1[1] - LS_W2 / 2, jx + LS_W3N / 2, d_n1[1] + LS_W2 / 2)
    _ls_vstrip(b, cell, jx, d_n1[1], yh, LS_W3N, land0=True)
    b._cut(cell, LS_VIA2, jx, d_n1[1])
    b._box(cell, LS_M2, d_p1[0], d_p1[1] - LS_W2 / 2, jx + LS_W3N / 2, d_p1[1] + LS_W2 / 2)
    b._cut(cell, LS_VIA2, jx, d_p1[1])
    _ls_pad3(b, cell, d_p1, via2=False)
    # The top run's east end stops at the drop leg's far edge (not its own
    # half-width past the junction): one more 0.06 um would close the gap
    # to the `out` vertical at XMp2.D+0.06 below 0.28 um.
    _ls_hstrip(b, cell, jx, g_p2[0] + LS_W3N / 2 - LS_W3 / 2, yh, LS_W3)
    _ls_vstrip(b, cell, g_p2[0], g_p2[1], yh, LS_W3N, land0=True)
    _ls_pad3(b, cell, g_p2)
    # out: XMn2.D west on M2 at pad height, M3 up to the channel, east on
    # M2, M3 up past XMp2.D (tapped there) to a top M3 run that drops west
    # into XMp1.G. XMp2.D's M1 pad centre is 0.06 um west of the column's
    # free M3 x (XMp1.D pads XMn1.D by 0.2 um), so the tap's via stack sits
    # at pad+0.06: still inside the 0.42 um pad, and 0.30 um clear of the
    # x1 stub that drops into XMp2.G.
    d_n2, d_p2, g_p1 = n2["U0_D"], p2["U0_D"], p1["U0_G"]
    jx = LS_JUNC_X["out"]
    mx = d_p2[0] + 0.06  # M3 x through XMp2.D
    ym, yh = LS_TRACK_Y["out"], LS_M3_HORIZ_Y["out"]
    _ls_pad3(b, cell, d_n2, via2=False)
    b._box(cell, LS_M2, jx - LS_W3N / 2, d_n2[1] - LS_W2 / 2, d_n2[0], d_n2[1] + LS_W2 / 2)
    _ls_vstrip(b, cell, jx, d_n2[1], ym, LS_W3N, land0=True, land1=True)
    b._cut(cell, LS_VIA2, jx, d_n2[1])
    b._box(cell, LS_M2, jx - LS_W3N / 2, ym - LS_W2 / 2, mx + LS_W3N / 2, ym + LS_W2 / 2)
    b._cut(cell, LS_VIA2, jx, ym)
    _ls_vstrip(b, cell, mx, ym, yh, LS_W3N, land0=True)
    b._cut(cell, LS_VIA2, mx, ym)
    _ls_pad3(b, cell, d_p2, via2_x=mx)
    _ls_hstrip(b, cell, g_p1[0], mx, yh, LS_W3)
    _ls_vstrip(b, cell, g_p1[0], g_p1[1], yh, LS_W3N, land0=True)
    _ls_pad3(b, cell, g_p1)


def _ls_labels(b, cell, ports):
    for net, iname, port in (("in", "XMni", "U0_G"), ("inb", "XMni", "U0_D"),
                             ("x1", "XMn1", "U0_D"), ("out", "XMn2", "U0_D"),
                             ("vdd33", "XMpi", "TAP_W"), ("vprog", "XMp1", "TAP_S"),
                             ("vss", "XMn1", "TAP_S")):
        x, y = ports[iname][port][0], ports[iname][port][1]
        b._label(cell, net, x, y)


def _ls_pad3(b, cell, port, via2_x=None, via2=True):
    """via1 + M2 landing pad + via2 at one M1 pad centre.

    via2_x shifts only the upper cut (M2 pad still centres on the M1
    pad): used where the M3 stub through a 0.42 um pad must clear a
    neighbouring net's M3 by 0.28 um (XMp2.D). via2=False omits the cut
    where the net's M3 does not run over this pad (the D pads: their M2
    runs to the junction, which carries its own via2); a cut with no M3
    above it is an unlanded via (V2.3c/d, V2.4b/c: unmodeled in the deck,
    gated by layout/check_via2_landing.sh).
    """
    cx, cy = port[0], port[1]
    h = LS_PAD2 / 2
    b._cut(cell, LS_VIA1, cx, cy)
    b._box(cell, LS_M2, cx - h, cy - h, cx + h, cy + h)
    if via2:
        b._cut(cell, LS_VIA2, via2_x if via2_x is not None else cx, cy)


def _ls_vstrip(b, cell, x, y0, y1, w, land0=False, land1=False):
    """Vertical M3 strip between two endpoints, a w/2 shoulder past each
    end. land0/land1 mark an end whose endpoint centres a via2 cut: that
    shoulder alone leaves w/2 - 0.13 um of end overlap (0.02 um on
    LS_W3N), so the strip reaches LS_V2_END past the endpoint instead."""
    # Each land flag stays with its own endpoint whichever order the
    # caller passes them in: sort (y, flag) pairs, not the bare ys.
    (lo, land_lo), (hi, land_hi) = sorted([(y0, land0), (y1, land1)],
                                          key=lambda p: p[0])
    e = max(0.0, LS_V2_END - w / 2)
    b._box(cell, LS_M3, x - w / 2, lo - w / 2 - (e if land_lo else 0.0),
           x + w / 2, hi + w / 2 + (e if land_hi else 0.0))


def _ls_hstrip(b, cell, x0, x1, y, w):
    lo, hi = min(x0, x1), max(x0, x1)
    b._box(cell, LS_M3, lo - w / 2, y - w / 2, hi + w / 2, y + w / 2)
