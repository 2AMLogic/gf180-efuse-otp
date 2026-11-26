#!/usr/bin/env python3
"""efuse_bitcell / efuse_row / efuse_otp_array routing.

bitcell_cell, the eight-bit array_row_cell and the M2-M5 route_array_top,
with their local floorplan constants and top-level via-array helpers (see
layout/README.md, "efuse_bitcell / efuse_row routing" and "efuse_otp_array
top-level routing"). The top router taps the other cells' rails at the
heights their own modules state: LS_VSS_RAIL_Y (route_ls.py), CD_RAIL_Y
(route_drivers.py) and CS_RAIL_Y (route_sense.py).
"""

import klayout.db as kdb

from analog_core import (DBU_UM, LS_M1, LS_M1_LBL, LS_M2, LS_M3, LS_VIA1,
                         LS_VIA2, LS_W2, LS_W3, gs)
from route_drivers import CD_RAIL_Y
from route_ls import LS_VSS_RAIL_Y
from route_sense import CS_RAIL_Y

# efuse_bitcell / efuse_row routing (bitcell_cell, array_row_cell; see
# layout/README.md, "efuse_bitcell / efuse_row routing"). All values um.
BC_SEL_X = 13.285  # select (rotated 180 deg) bbox west edge: fuse east edge + 2.005
BC_PAD_Y = 2.19  # centre y of both fuse M1 pads (asserted against the PDK cell)
BC_BL_CUT_X = (0.60, 1.24, 1.88)  # three columns clear of the fuse marker
BC_BL_LANE_Y0 = -1.35  # bl M3 lane south end (crosses the wl rail below the cell)
BC_N_FUSE_CUT_DX = (-1.99, -1.35, -0.71)  # via1s on the fuse out pad, from its east edge
BC_N_SEL_CUT_DX = tuple(0.175 + 0.64 * i for i in range(12))  # via1s on the drain strap, from its exit pad
BC_WL_STUB_Y0 = -1.24  # wl M2 stub down to the row rail (rail top edge)
BC_VSS_CUT_DY = tuple(0.64 * i for i in range(10))  # distributed along the east M1 guard-ring strap
ROW_WL_RAIL_Y = (-1.24, -0.82)  # M2 word-line rail under the bitcells
ROW_VSS_RAIL_Y = (7.25, 7.67)  # M2 return rail through the select row

# Top-level array routing (route_array_top and layout/README.md,
# "efuse_otp_array top-level routing"). Uses the upper planes M4 (horizontal
# buses and local landing bars) and M5 (MetalTop on 5LM gf180mcuC: vertical
# bit-line, supply and signal trunks), plus short M2 word-line bridges in the
# rowdrv-to-row gap. Every subcell uses M1-M3 only, so M4/M5 are unobstructed.
TOP_VIA3, TOP_M4 = (40, 0), (46, 0)
TOP_VIA4, TOP_M5 = (41, 0), (81, 0)
TOP_VIA_PITCH = 0.64  # 0.38 um space >= 0.36 um (V2/V3/V4.2b for >=4x4 arrays)
TOP_M4_SIG_W = 0.50  # M4 signal bus width (>= 0.28 M4.1; >= 0.12 via enclosure)
TOP_M5_SIG_W = 0.80  # M5 signal drop width (>= 0.44 9K MT.1; >= 0.5625 um^2 MT.4)
TOP_TRUNK_W = 10.0  # per-column vertical M5 trunks (bl, vss, vprog; <= 10 um avoids MT.2b)
TOP_BUS_W = 24.0  # south horizontal main M4 supply buses (vss, vprog; < 30 um MSLOT.1)
TOP_VDD_BUS_W = 4.0  # south horizontal main M4 vdd33 bus
TOP_RD_RAIL_W = 2.0  # west vertical M4/M5 supply rails over efuse_rowdrv
TOP_BL_BAR_W = 4.0  # per-column horizontal M4 bl jumper over efuse_coldrv
TOP_VPROG_BAR_W = 1.60  # per-column horizontal M4 vprog jumper over efuse_coldrv
TOP_VDD_FEED_W = 1.20  # per-column vertical M5 vdd33 feeder
TOP_VSS_COL_X = (24.0, 34.0)  # column-local M5 vss trunk x span (beside bitcell vss exit)
TOP_VPROG_COL_X = (60.0, 70.0)  # column-local M5 vprog feeder x span
TOP_VDD_COL_X = 110.0  # column-local M5 vdd33 feeder centre x (M3-free over coldrv & sense)
TOP_SIG_Y = {"prog_strobe": -15.0, "sense_en": -18.0}
TOP_SA_TAP_Y = {"sense_en": -50.0, "sbl": -44.0}
TOP_BUS_Y = {"vss": (-90.0, -66.0), "vprog": (-116.0, -92.0), "vdd33": (-122.0, -118.0)}

# Expected shape of the array top, asserted against the netlist.
ROWS, COLS = 32, 8


def bitcell_cell(b, subckt):
    """efuse_bitcell: the PDK fuse and the rotated select NFET, routed.

    Floorplan (um, this cell's own coordinates): the fuse at the origin
    (bbox 11.28 x 4.38, PDK geometry untouched, `verify_fuse` guards it);
    the select NFET east of it rotated 180 deg, so its 0.42 um drain
    strap exit faces west at the same height as the fuse out pad --
    The fuse output reaches the select drain over M2. Nine via1 cuts
    on the output-pad landing and twelve on the drain strap distribute
    program current. A three-by-three via1/via2 bank west of the marker
    feeds the M3 bit line. The gate stub drops to the M2 word-line rail.
    The source connects to the guard ring and M2 return rail. The array
    router also connects the source strap to its neighboring M5 trunk.
    The fuse cell's own 'in'/'out' 34/10 texts
    are dropped: they would rename the bl/n pad nets at extraction
    (verify_fuse compares geometry; its Region sides ignore texts).
    """
    insts = {i["name"]: i for i in b.netlist[subckt]}
    assert set(insts) == {"XXf", "XXsel"}, f"{subckt} netlist changed: {sorted(insts)}"
    f, s = insts["XXf"], insts["XXsel"]
    assert f["kind"] == "x" and f["master"] == "efuse" and f["nodes"] == ["bl", "n"], \
        f"{subckt}: XXf is no longer 'bl n efuse'"
    assert s["kind"] == "x" and s["master"] == "nfet_06v0" \
        and s["nodes"] == ["n", "wl", "vss", "vss"], \
        f"{subckt}: XXsel is no longer 'n wl vss vss nfet_06v0'"
    cell = b.layout.create_cell(subckt)
    for pair in (LS_M2, LS_VIA1, LS_M3, LS_VIA2):
        b.layout.layer(*pair)

    # fuse: bbox lower-left at the origin; the two M1 pad boxes and the
    # 'in'/'out' texts are read from the imported PDK cell itself.
    fuse = b.leaf(subckt, f)
    lbl_i, m1_i = b.layout.layer(*LS_M1_LBL), b.layout.layer(*LS_M1)
    pads = {}
    for t in list(fuse.shapes(lbl_i).each()):
        p = t.text.trans.disp
        for bx in fuse.shapes(m1_i).each():
            if bx.box.contains(p):
                pads[t.text.string] = bx.box
        fuse.shapes(lbl_i).erase(t)
    assert set(pads) == {"in", "out"}, "PDK fuse cell must carry in/out pad texts"
    dx0, dy0 = b.place(cell, fuse, 0.0, 0.0)
    t0 = kdb.Trans(round(dx0 / DBU_UM), round(dy0 / DBU_UM))
    pin, pout = pads["in"].transformed(t0), pads["out"].transformed(t0)
    yc = pin.center().y * DBU_UM
    assert abs(yc - BC_PAD_Y) < 1e-9 and abs(pout.center().y * DBU_UM - yc) < 1e-9, \
        "fuse M1 pads no longer share a centre height"

    # select, rotated 180 deg: U0_D faces west at pad height, U0_G exits
    # south, TAP_W is the ring's east strap.
    sel = b.leaf(subckt, s)
    rep = b.reports[f"{subckt}__Xsel"]
    b.add_program_diffusion_contacts(sel, rep["ports"])
    dx1, dy1 = b.place(cell, sel, BC_SEL_X, 0.0, rot=2)
    t1 = kdb.Trans(2, False, round(dx1 / DBU_UM), round(dy1 / DBU_UM))

    def port(name):
        p = next(p for p in rep["ports"] if p["name"] == name)
        v = t1 * kdb.Point(round(p["x_um"] / DBU_UM), round(p["y_um"] / DBU_UM))
        return gs(v.x * DBU_UM), gs(v.y * DBU_UM)

    d, g, se, tw = port("U0_D"), port("U0_G"), port("U0_S"), port("TAP_W")
    assert abs(d[1] - 2.26) < 1e-9 and abs(d[1] - yc) <= 0.075, \
        "select drain strap no longer faces the fuse out pad"

    # Use the metal to the east of the marker for the fuse output tap.
    fx = [gs(pout.right * DBU_UM + dx) for dx in BC_N_FUSE_CUT_DX]
    dxs = [gs(d[0] + dx) for dx in BC_N_SEL_CUT_DX]
    fys = _via_center_span(BC_PAD_Y, 3)
    for x in fx:
        for y in fys:
            b._cut(cell, LS_VIA1, x, y)
    b._box(cell, LS_M2, fx[0] - 0.21, fys[0] - 0.21,
              fx[-1] + 0.21, fys[-1] + 0.21)
    _via_grid(b, cell, LS_VIA1, dxs, [d[1]])
    b._box(cell, LS_M2, fx[0] - 0.21, BC_PAD_Y - 0.21,
              dxs[-1] + 0.21, d[1] + 0.21)
    # The input bank stays west of the marker. M3 carries the bit line.
    bcx = [gs(pin.left * DBU_UM + x) for x in BC_BL_CUT_X]
    bys = _via_center_span(BC_PAD_Y, 3)
    for metal in (LS_M1, LS_M2):
        b._box(cell, metal, bcx[0] - 0.21, bys[0] - 0.21,
                  bcx[-1] + 0.21, bys[-1] + 0.21)
    for via in (LS_VIA1, LS_VIA2):
        _via_grid(b, cell, via, bcx, bys)
    b._box(cell, LS_M3, bcx[0] - 0.21, BC_BL_LANE_Y0,
              bcx[-1] + 0.21, bys[-1] + 0.21)
    # wl: via1 on the gate pad, M2 stub down to the row rail.
    b._cut(cell, LS_VIA1, g[0], g[1])
    b._box(cell, LS_M2, g[0] - 0.21, BC_WL_STUB_Y0, g[0] + 0.21, g[1] + 0.21)
    # Connect the source to the guard ring and distribute its row-return taps
    # along the east M1 strap. The array router adds a direct trunk return.
    b._box(cell, LS_M1, se[0] - 0.21, se[1] - 0.21, tw[0] + 0.21, se[1] + 0.21)
    ry = sum(ROW_VSS_RAIL_Y) / 2
    for dy in BC_VSS_CUT_DY:
        b._cut(cell, LS_VIA1, tw[0], gs(ry + dy))
    b._box(cell, LS_M2, tw[0] - 0.21, gs(ry - 0.21),
              tw[0] + 0.21, gs(ry + max(BC_VSS_CUT_DY) + 0.21))

    for net, x, y in (("bl", (bcx[0] + bcx[-1]) / 2, BC_PAD_Y),
                      ("n", pout.center().x * DBU_UM, BC_PAD_Y),
                      ("wl", g[0], g[1]), ("vss", tw[0], ry)):
        b._label(cell, net, gs(x), gs(y))
    # pin access points for the row and top-level routing (array_row_cell,
    # #307): the bl lane, the wl stub and the vss pad, all in-cell coords.
    b.bc_ports = {"bl": ((bcx[0] + bcx[-1]) / 2, BC_PAD_Y), "wl": g, "vss": (tw[0], ry), "source": se}
    b.cells[subckt] = cell
    return cell


def array_row_cell(b, pitch_x):
    """efuse_row: 8 bitcells at the column pitch plus the shared rails.

    One M2 wl rail below the bitcells (each gate stub drops into it) and
    one M2 vss rail through the select row (each bitcell's ring-east
    via1s land on it); both span the full row and exit west. The eight
    bl lanes are the bitcells' own M3 lanes, one per column, already
    crossing the wl rail on M3; bl[7] is the west-most column, matching
    the .subckt pin order (bl[7] first). Labels sit on M1 pads of the
    first bitcell's instances (wl, vss) and on each column's fuse in
    pad (bl[i]).
    """
    assert hasattr(b, "bc_ports"), "bitcell_cell must run before array_row_cell"
    cell = b.layout.create_cell("efuse_row")
    bit = b.cells["efuse_bitcell"]
    # Identity placement (target = the bitcell's own bbox origin, which is
    # on the grid): the rails below are stated in bitcell coordinates, so
    # the instances must not be shifted to a different origin.
    bb = bit.bbox()
    assert bb.left == 0, f"efuse_bitcell bbox left {bb.left} != 0"
    b.place(cell, bit, bb.left * DBU_UM, bb.bottom * DBU_UM, 1, COLS, pitch_x)
    w = gs((COLS - 1) * pitch_x + b.size(bit)[0])
    b._box(cell, LS_M2, 0.0, ROW_WL_RAIL_Y[0], w, ROW_WL_RAIL_Y[1])
    b._box(cell, LS_M2, 0.0, ROW_VSS_RAIL_Y[0], w, ROW_VSS_RAIL_Y[1])
    bp = b.bc_ports
    b._label(cell, "wl", bp["wl"][0], bp["wl"][1])
    b._label(cell, "vss", bp["vss"][0], bp["vss"][1])
    for k in range(COLS):
        b._label(cell, f"bl[{COLS - 1 - k}]", gs(bp["bl"][0] + k * pitch_x), bp["bl"][1])
    b.cells["efuse_row"] = cell
    return cell


def _via_grid(b, cell, layer, xs, ys):
    for x in xs:
        for y in ys:
            b._cut(cell, layer, x, y)


def _via_span(x0, n):
    return [gs(x0 + i * TOP_VIA_PITCH) for i in range(n)]


def _via_center_span(xc, n):
    return _via_span(xc - (n - 1) * TOP_VIA_PITCH / 2, n)


def _m2_to_m5_strip(b, cell, xs, y):
    """Horizontal row of stacked via2 + M3 pad + via3 + M4 pad + via4 on an
    existing M2 rail at y, landing into an overlying M5 trunk."""
    _via_grid(b, cell, LS_VIA2, xs, [y])
    b._box(cell, LS_M3, xs[0] - LS_W3 / 2, y - LS_W3 / 2,
           xs[-1] + LS_W3 / 2, y + LS_W3 / 2)
    _via_grid(b, cell, TOP_VIA3, xs, [y])
    b._box(cell, TOP_M4, xs[0] - LS_W3 / 2, y - LS_W3 / 2,
           xs[-1] + LS_W3 / 2, y + LS_W3 / 2)
    _via_grid(b, cell, TOP_VIA4, xs, [y])


def route_array_top(b, cell, row_xy, rd_xy, cd_xy, sa_xy, step_x, step_y):
    """Wire the 32 rows, 32 row drivers, 8 column drivers and sense block.

    Planes (no constituent cell is modified; every subcell uses M1-M3):
      * M2: 32 short L-shaped wl[r] bridges across the rowdrv-to-row gap.
      * M3: local landing pads on subcell M2 rails/pads (all in M3-free
        windows) transitioning via2 -> via3.
      * M4: horizontal shared buses (prog_strobe, sense_en, sbl), per-column
        local jumpers (bl, vprog over efuse_coldrv), vertical supply rails
        over efuse_rowdrv (y >= -4), and the three south horizontal main
        supply buses (vss 24 um, vprog 24 um, vdd33 4 um).
      * M5 (MetalTop on 5LM gf180mcuC): vertical per-column trunks (10 um
        bl[c] and vss, 10 um vprog feeder, 1.2 um vdd33 feeder), west
        row-driver supply drops, and 0.8 um sense_en / sbl drops to
        efuse_sense.
    Column k (0..7 west to east) carries index c = COLS - 1 - k (7..0),
    matching efuse_row's pin order and Xcd[c] / Xarr[r] in the netlist.
    """
    for pair in (TOP_VIA3, TOP_M4, TOP_VIA4, TOP_M5):
        b.layout.layer(*pair)

    dx_row, dy_row = row_xy
    dx_rd, dy_rd = rd_xy
    dx_cd, dy_cd = cd_xy
    dx_sa, dy_sa = sa_xy
    lp, bp = b.ls_ports, b.bc_ports
    cd_pins, cd_lbl, cd_ty, cd_rx = (
        b.cd_ports["net_pins"], b.cd_ports["label_at"],
        b.cd_ports["track_y"], b.cd_ports["rail_x"])
    sa_pins, sa_lbl = b.sa_ports["net_pins"], b.sa_ports["label_at"]

    # 1. Word lines wl[0..31] (M2 L-bridges in the rowdrv-to-row gap) and
    #    row_sel[0..31] top-level M1 pin labels.
    x_jog = -1.00
    rd_wl_x = gs(dx_rd + lp["XMn2"]["U0_D"][0])
    for r in range(ROWS):
        y_rd_wl = gs(dy_rd + r * step_y + lp["XMn2"]["U0_D"][1])
        y_row_wl = gs(dy_row + r * step_y + sum(ROW_WL_RAIL_Y) / 2)
        b._box(cell, LS_M2, rd_wl_x, y_rd_wl - LS_W2 / 2,
               x_jog + LS_W2 / 2, y_rd_wl + LS_W2 / 2)
        b._box(cell, LS_M2, x_jog - LS_W2 / 2,
               min(y_row_wl, y_rd_wl) - LS_W2 / 2,
               x_jog + LS_W2 / 2, max(y_row_wl, y_rd_wl) + LS_W2 / 2)
        b._box(cell, LS_M2, x_jog - LS_W2 / 2, y_row_wl - LS_W2 / 2,
               dx_row + 0.50, y_row_wl + LS_W2 / 2)
        b._label(cell, f"wl[{r}]", gs(dx_row + bp["wl"][0]),
                 gs(dy_row + r * step_y + bp["wl"][1]))
        b._label(cell, f"row_sel[{r}]", gs(dx_rd + lp["XMni"]["U0_G"][0]),
                 gs(dy_rd + r * step_y + lp["XMni"]["U0_G"][1]))

    # 2. Row-driver vertical supply rails (M4 over the 32 row drivers,
    #    transitioning to M5 at y=-4..-2 down to the south M4 supply buses).
    rd_rails = (
        ("vdd33", -0.80, lp["XMpi"]["TAP_W"][1]),
        ("vss", 4.00, LS_VSS_RAIL_Y),
        ("vprog", 9.50, lp["XMp1"]["TAP_S"][1]),
    )
    rd_rail_x = {}
    for net, x_loc, y_loc in rd_rails:
        xc = gs(dx_rd + x_loc)
        rd_rail_x[net] = xc
        for r in range(ROWS):
            yc = gs(dy_rd + r * step_y + y_loc)
            b._cut(cell, LS_VIA2, xc, yc)
            b._box(cell, LS_M3, xc - LS_W3 / 2, yc - LS_W3 / 2,
                   xc + LS_W3 / 2, yc + LS_W3 / 2)
            b._cut(cell, TOP_VIA3, xc, yc)
        y_top = gs(dy_rd + (ROWS - 1) * step_y + y_loc + LS_W3 / 2)
        b._box(cell, TOP_M4, xc - TOP_RD_RAIL_W / 2, -4.00,
               xc + TOP_RD_RAIL_W / 2, y_top)
        vxs = _via_center_span(xc, 2)
        _via_grid(b, cell, TOP_VIA4, vxs, _via_center_span(-3.00, 3))
        by0, by1 = TOP_BUS_Y[net]
        b._box(cell, TOP_M5, xc - TOP_RD_RAIL_W / 2, by0,
               xc + TOP_RD_RAIL_W / 2, -2.00)
        _via_grid(b, cell, TOP_VIA4, vxs,
                  _via_center_span((by0 + by1) / 2, 3))

    # 3. Per-column bit lines bl[7..0] (10 um M5 vertical trunks + 4 um M4
    #    jumpers over efuse_coldrv) and col_sel[7..0] labels.
    y_bl_track = gs(dy_cd + cd_ty["bl"])
    y_bl_bar0 = gs(y_bl_track - TOP_BL_BAR_W / 2)
    y_bl_bar1 = gs(y_bl_track + TOP_BL_BAR_W / 2)
    y_bl_top = gs(dy_row + (ROWS - 1) * step_y + BC_PAD_Y + 0.21)
    mdrv_dx = [p[0] for p in cd_pins["bl"][:3]]
    assert len(mdrv_dx) == 3, f"expected 3 Mdrv drain lanes, got {mdrv_dx}"
    bl_cut_x = [gs(x) for x in BC_BL_CUT_X]
    for k in range(COLS):
        c = COLS - 1 - k
        x_col = gs(dx_row + k * step_x)
        x_cd = gs(dx_cd + k * step_x)
        # M5 trunk covering all 32 rows' bl M3 lanes
        b._box(cell, TOP_M5, x_col, y_bl_bar0,
               x_col + TOP_TRUNK_W, y_bl_top)
        for r in range(ROWS):
            ys = [gs(dy_row + r * step_y + BC_BL_LANE_Y0 + 0.60 + j * TOP_VIA_PITCH)
                  for j in range(4)]
            xs = [gs(x_col + x) for x in bl_cut_x]
            _via_grid(b, cell, TOP_VIA3, xs, ys)
            b._box(cell, TOP_M4, xs[0] - 0.21, ys[0] - 0.21,
                   xs[-1] + 0.21, ys[-1] + 0.21)
            _via_grid(b, cell, TOP_VIA4, xs, ys)
        # Tap efuse_coldrv[k]'s bl M2 track beside all three Mdrv drains
        for mx in mdrv_dx:
            cxs = _via_span(x_cd + mx + 1.20, 4)
            _via_grid(b, cell, LS_VIA2, cxs, [y_bl_track])
            b._box(cell, LS_M3, cxs[0] - LS_W3 / 2, y_bl_track - LS_W3 / 2,
                   cxs[-1] + LS_W3 / 2, y_bl_track + LS_W3 / 2)
            _via_grid(b, cell, TOP_VIA3, cxs, [y_bl_track])
        x_bar1 = gs(x_cd + mdrv_dx[-1] + 1.20 + 3 * TOP_VIA_PITCH + LS_W3 / 2 + 0.20)
        b._box(cell, TOP_M4, x_col, y_bl_bar0, x_bar1, y_bl_bar1)
        _via_grid(b, cell, TOP_VIA4, _via_span(x_col + 1.50, 5),
                  _via_center_span(y_bl_track, 3))
        b._label(cell, f"bl[{c}]", gs(x_cd + cd_lbl["bl"][0]),
                 gs(dy_cd + cd_lbl["bl"][1]))
        b._label(cell, f"col_sel[{c}]", gs(x_cd + cd_lbl["col_sel"][0]),
                 gs(dy_cd + cd_lbl["col_sel"][1]))

    # 4. Shared control & sense buses: prog_strobe, sense_en, sbl (M4
    #    horizontal across all 8 column drivers; M5 drops to efuse_sense).
    ps_x = cd_pins["prog_strobe"][0][0]
    y_ps = TOP_SIG_Y["prog_strobe"]
    b._box(cell, TOP_M4, gs(dx_cd + ps_x - TOP_M4_SIG_W / 2),
           y_ps - TOP_M4_SIG_W / 2,
           gs(dx_cd + (COLS - 1) * step_x + ps_x + TOP_M4_SIG_W / 2),
           y_ps + TOP_M4_SIG_W / 2)
    for k in range(COLS):
        b._cut(cell, TOP_VIA3, gs(dx_cd + k * step_x + ps_x), y_ps)

    se_cd_x = cd_pins["sense_en"][0][0]
    sa_se_x = gs(dx_sa + sa_pins["sense_en"][0][0])
    y_se = TOP_SIG_Y["sense_en"]
    b._box(cell, TOP_M4, sa_se_x - TOP_M4_SIG_W / 2, y_se - TOP_M4_SIG_W / 2,
           gs(dx_cd + (COLS - 1) * step_x + se_cd_x + TOP_M4_SIG_W / 2),
           y_se + TOP_M4_SIG_W / 2)
    for k in range(COLS):
        b._cut(cell, TOP_VIA3, gs(dx_cd + k * step_x + se_cd_x), y_se)
    y_sa_se = TOP_SA_TAP_Y["sense_en"]
    b._cut(cell, TOP_VIA3, sa_se_x, y_sa_se)
    b._box(cell, TOP_M4, sa_se_x - TOP_M4_SIG_W / 2, y_sa_se - TOP_M4_SIG_W / 2,
           sa_se_x + TOP_M4_SIG_W / 2, y_sa_se + TOP_M4_SIG_W / 2)
    b._cut(cell, TOP_VIA4, sa_se_x, y_sa_se)
    b._cut(cell, TOP_VIA4, sa_se_x, y_se)
    b._box(cell, TOP_M5, sa_se_x - TOP_M5_SIG_W / 2, y_sa_se - TOP_M5_SIG_W / 2,
           sa_se_x + TOP_M5_SIG_W / 2, y_se + TOP_M5_SIG_W / 2)

    sbl_cd_x = gs(cd_pins["sbl"][0][0] + 0.08)  # centre of Mrs.S M2 pad
    y_sbl = gs(dy_cd + cd_pins["sbl"][0][1])
    sa_sbl_x = gs(dx_sa + sa_pins["sbl"][-1][0])  # comparator-side M3 lane
    b._box(cell, TOP_M4, sa_sbl_x - TOP_M4_SIG_W / 2, y_sbl - TOP_M4_SIG_W / 2,
           gs(dx_cd + (COLS - 1) * step_x + sbl_cd_x + TOP_M4_SIG_W / 2),
           y_sbl + TOP_M4_SIG_W / 2)
    for k in range(COLS):
        xc = gs(dx_cd + k * step_x + sbl_cd_x)
        b._cut(cell, LS_VIA2, xc, y_sbl)
        b._box(cell, LS_M3, xc - LS_W3 / 2, y_sbl - LS_W3 / 2,
               xc + LS_W3 / 2, y_sbl + LS_W3 / 2)
        b._cut(cell, TOP_VIA3, xc, y_sbl)
    y_sa_sbl = TOP_SA_TAP_Y["sbl"]
    b._cut(cell, TOP_VIA3, sa_sbl_x, y_sa_sbl)
    b._box(cell, TOP_M4, sa_sbl_x - TOP_M4_SIG_W / 2, y_sa_sbl - TOP_M4_SIG_W / 2,
           sa_sbl_x + TOP_M4_SIG_W / 2, y_sa_sbl + TOP_M4_SIG_W / 2)
    b._cut(cell, TOP_VIA4, sa_sbl_x, y_sa_sbl)
    b._cut(cell, TOP_VIA4, sa_sbl_x, y_sbl)
    b._box(cell, TOP_M5, sa_sbl_x - TOP_M5_SIG_W / 2, y_sa_sbl - TOP_M5_SIG_W / 2,
           sa_sbl_x + TOP_M5_SIG_W / 2, y_sbl + TOP_M5_SIG_W / 2)

    # 5. Per-column supply trunks (M5) and south horizontal main buses (M4):
    #    vss (10 um M5 per column beside every bitcell's vss exit, 24 um M4 bus),
    #    vprog (10 um M5 per column into all 3 Mdrv taps, 24 um M4 bus),
    #    vdd33 (1.2 um M5 per column, 4 um M4 bus).
    y_vss_top = gs(dy_row + (ROWS - 1) * step_y + b.bc_ports["source"][1] + 0.40)
    y_cd_vss = gs(dy_cd + CD_RAIL_Y["vss"])
    y_cd_vdd = gs(dy_cd + CD_RAIL_Y["vdd33"])
    y_cd_vp = gs(dy_cd + CD_RAIL_Y["vprog"])
    mdrv_vp_x = cd_rx["vprog"][1:]
    assert len(mdrv_vp_x) == 3, f"expected 3 Mdrv vprog taps, got {mdrv_vp_x}"
    vss_by0, vss_by1 = TOP_BUS_Y["vss"]
    vp_by0, vp_by1 = TOP_BUS_Y["vprog"]
    vdd_by0, vdd_by1 = TOP_BUS_Y["vdd33"]
    for k in range(COLS):
        x_col = gs(dx_row + k * step_x)
        x_cd = gs(dx_cd + k * step_x)

        # vss trunk
        vx0, vx1 = gs(x_col + TOP_VSS_COL_X[0]), gs(x_col + TOP_VSS_COL_X[1])
        b._box(cell, TOP_M5, vx0, vss_by0, vx1, y_vss_top)
        row_vss_xs = _via_span(x_col + 24.50, 8)
        row_east = gs(dx_row + b.size(b.cells["efuse_row"])[0])
        for r in range(ROWS):
            y_r_vss = gs(dy_row + r * step_y + sum(ROW_VSS_RAIL_Y) / 2)
            if k == COLS - 1:
                # efuse_row's vss rail ends at bitcell 7's east edge (973.815);
                # extend it east on M2 under column 7's vss trunk so all 8 via2s land.
                b._box(cell, LS_M2, row_east - 0.50,
                       gs(dy_row + r * step_y + ROW_VSS_RAIL_Y[0]),
                          vx1, gs(dy_row + r * step_y + ROW_VSS_RAIL_Y[1]))
            _m2_to_m5_strip(b, cell, row_vss_xs, y_r_vss)
            # The select source can return directly into its adjacent
            # power trunk as well as through the guard ring and row rail.
            src_x, src_y = b.bc_ports["source"]
            src_y = gs(dy_row + r * step_y + src_y)
            src_xs = _via_span(gs(x_col + src_x - 6.40), 9)
            _via_grid(b, cell, LS_VIA1, src_xs, [src_y])
            b._box(cell, LS_M2, src_xs[0] - 0.21, src_y - 0.21,
                      row_vss_xs[-1] + 0.21, src_y + 0.21)
            _m2_to_m5_strip(b, cell, row_vss_xs, src_y)
        _m2_to_m5_strip(b, cell, _via_span(x_cd + 24.00, 6), y_cd_vss)
        _via_grid(b, cell, TOP_VIA4,
                  _via_center_span((vx0 + vx1) / 2, 6),
                  _via_center_span((vss_by0 + vss_by1) / 2, 6))

        # vprog feeder
        px0, px1 = gs(x_col + TOP_VPROG_COL_X[0]), gs(x_col + TOP_VPROG_COL_X[1])
        b._box(cell, TOP_M5, px0, vp_by0, px1, y_cd_vp + TOP_VPROG_BAR_W / 2)
        for start_x in (mdrv_vp_x[0] + 1.20, mdrv_vp_x[1] - 5.00,
                        mdrv_vp_x[1] + 1.20, mdrv_vp_x[2] - 4.40):
            cxs = _via_span(x_cd + start_x, 6)
            _via_grid(b, cell, LS_VIA2, cxs, [y_cd_vp])
            b._box(cell, LS_M3, cxs[0] - LS_W3 / 2, y_cd_vp - LS_W3 / 2,
                   cxs[-1] + LS_W3 / 2, y_cd_vp + LS_W3 / 2)
            _via_grid(b, cell, TOP_VIA3, cxs, [y_cd_vp])
        b._box(cell, TOP_M4, gs(x_cd + mdrv_vp_x[0] + 0.99),
               y_cd_vp - TOP_VPROG_BAR_W / 2,
               gs(x_cd + mdrv_vp_x[2] - 0.99),
               y_cd_vp + TOP_VPROG_BAR_W / 2)
        _via_grid(b, cell, TOP_VIA4,
                  _via_center_span((px0 + px1) / 2, 10),
                  _via_center_span(y_cd_vp, 2))
        _via_grid(b, cell, TOP_VIA4,
                  _via_center_span((px0 + px1) / 2, 6),
                       _via_center_span((vp_by0 + vp_by1) / 2, 6))

        # Contact the three individual driver straps. The source drops
        # to the supply bar on M4. Drain metal rises on M3 so it can
        # cross the horizontal control buses before landing on M4.
        for xc, sy, drain_y in b.cd_ports["mdrv_straps"]:
            for side in (-1, 1):
                xs = _via_center_span(gs(x_cd + xc + side * 3.10), 6)
                x0, x1 = xs[0] - 0.21, xs[-1] + 0.21
                for which, y in (("src", gs(dy_cd + sy)), ("drain", gs(dy_cd + drain_y))):
                    for via in (LS_VIA1, LS_VIA2):
                        _via_grid(b, cell, via, xs, [y])
                    b._box(cell, LS_M2, x0, y - 0.21, x1, y + 0.21)
                    if which == "src":
                        b._box(cell, LS_M3, x0, y - 0.21, x1, y + 0.21)
                        _via_grid(b, cell, TOP_VIA3, xs, [y])
                        b._box(cell, TOP_M4, x0 - 0.04, y_cd_vp - 0.25, x1 + 0.04, y + 0.25)
                    else:
                        b._box(cell, LS_M3, x0, y - 0.21, x1, y_bl_track + 0.21)
                        _via_grid(b, cell, TOP_VIA3, xs, [y_bl_track])
            # Join both source branches to the column feeder bar.
            b._box(cell, TOP_M4, x_cd + xc - 4.95, y_cd_vp - 0.60,
                      x_cd + xc + 4.95, y_cd_vp + 0.60)

        # vdd33 feeder
        dx_c = gs(x_col + TOP_VDD_COL_X)
        b._box(cell, TOP_M5, dx_c - TOP_VDD_FEED_W / 2, vdd_by0,
               dx_c + TOP_VDD_FEED_W / 2, y_cd_vdd + 0.42)
        vdd_xs = _via_center_span(dx_c, 2)
        _m2_to_m5_strip(b, cell, vdd_xs, y_cd_vdd)
        _via_grid(b, cell, TOP_VIA4, vdd_xs,
                  _via_center_span((vdd_by0 + vdd_by1) / 2, 2))

        # efuse_sense supply taps (column 0 passes directly over efuse_sense)
        if k == 0:
            y_sa_vss = gs(dy_sa + CS_RAIL_Y["vss"])
            _m2_to_m5_strip(b, cell, _via_span(dx_sa + 25.00, 4), y_sa_vss)
            y_sa_vdd = gs(dy_sa + CS_RAIL_Y["vdd33"])
            _m2_to_m5_strip(b, cell, vdd_xs, y_sa_vdd)
            sa_vp_x = gs(dx_sa + sa_pins["vprog"][0][0])
            sa_vp_y = gs(dy_sa + sa_pins["vprog"][0][1])
            # The M1 labels are external power landings. Carry program
            # current from each landing directly to a wide supply route.
            sa_gnd_x = gs(dx_sa + sa_lbl["vss"][0])
            sa_gnd_y = gs(dy_sa + sa_lbl["vss"][1])
            for net, x, y, count in (("vprog", sa_vp_x, sa_vp_y, 11),
                                     ("vss", sa_gnd_x, sa_gnd_y, 7)):
                xs = _via_center_span(x, count)
                ys = [y] if net == "vprog" else [gs(y - TOP_VIA_PITCH), y]
                for layer in (LS_M1, LS_M2, LS_M3):
                    b._box(cell, layer, xs[0] - 0.21, min(ys) - 0.21,
                              xs[-1] + 0.21, max(ys) + 0.21)
                for vy in ys:
                    extra = [cx for cx in xs if (cx, vy) != (x, y)]
                    # Each sense port already has a center via1 and the
                    # ground port also has a center via2.
                    _via_grid(b, cell, LS_VIA1, extra, [vy])
                    _via_grid(b, cell, LS_VIA2, xs if net == "vprog" else extra, [vy])
                _via_grid(b, cell, TOP_VIA3, xs, ys)
                if net == "vss":
                    b._box(cell, TOP_M4, xs[0] - 0.25, vss_by1 - 0.25,
                              xs[-1] + 0.25, y + 0.25)
                else:
                    b._box(cell, TOP_M4, xs[0] - 0.25, y - TOP_VPROG_BAR_W / 2,
                              px1, y + TOP_VPROG_BAR_W / 2)
                    _via_grid(b, cell, TOP_VIA4,
                                   _via_center_span((px0 + px1) / 2, 10),
                                   _via_center_span(y, 2))

    # Three south horizontal main M4 supply buses tying all columns & west rails
    b._box(cell, TOP_M4, rd_rail_x["vss"] - TOP_RD_RAIL_W / 2, vss_by0,
           gs(dx_row + (COLS - 1) * step_x + TOP_VSS_COL_X[1]), vss_by1)
    b._box(cell, TOP_M4, rd_rail_x["vprog"] - TOP_RD_RAIL_W / 2, vp_by0,
           gs(dx_row + (COLS - 1) * step_x + TOP_VPROG_COL_X[1]), vp_by1)
    b._box(cell, TOP_M4, rd_rail_x["vdd33"] - TOP_RD_RAIL_W / 2, vdd_by0,
           gs(dx_row + (COLS - 1) * step_x + TOP_VDD_COL_X + TOP_VDD_FEED_W / 2),
           vdd_by1)

    # 6. Top-level port labels on M1 label layer (34/10).
    b._label(cell, "prog_strobe", gs(dx_cd + cd_lbl["prog_strobe"][0]),
             gs(dy_cd + cd_lbl["prog_strobe"][1]))
    for net in ("sense_en", "clk", "sense_out", "sbl", "vdd33", "vprog", "vss"):
        b._label(cell, net, gs(dx_sa + sa_lbl[net][0]),
                 gs(dy_sa + sa_lbl[net][1]))
