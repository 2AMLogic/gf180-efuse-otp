#!/usr/bin/env python3
"""efuse_comp / efuse_sense routing: one row, lanes up, tracks above, rails below.

comp_cell and sense_cell, their row-placement and channel helpers (_row_unit,
_unit_pins, _row_channels, _row_place_all) -- see layout/README.md,
"efuse_comp routing" / "efuse_sense routing". Both cells reuse the coldrv
planes and pitches (route_drivers.py): one row of leaf devices (efuse_comp:
seven MOS; efuse_sense: twenty leaves and the routed efuse_comp instance
among them, in netlist order), one via1 + M2 pad + via2 + vertical M3 lane
per signal pin, one M2 track per multi-pin net in a channel above the row,
and the M2 supply rails below it (same y as efuse_ls's own vss rail, so
efuse_sense's rails merge with the efuse_comp instance's where they cross
it).
"""

import klayout.db as kdb

from analog_core import (DBU_UM, GAP_UM, LS_M2, LS_M3, LS_VIA2, LS_W2, LS_W3N,
                         gs, snap)
from route_drivers import CD_SHIFT, CD_TRACK_PITCH, SUPPLY

# End-of-line reach of a narrow (< 0.34 um) M3 lane past a via2 centre in the
# comp/sense row routing: the 0.26 um cut's half size plus the 0.06 um V2.4b
# end-of-line overlap (V2.4c is met by the same extension), rounded up to 0.20.
M3_END = 0.20
CS_RAIL_Y = {"vss": -1.5, "vdd33": -2.22}  # M2 supply rails below the row
CS_EXPORT = 0.9  # efuse_comp's pin lanes extend this far above its channel


def _row_unit(b, cell, subckt, inst, x):
    """Place one row unit with its bbox lower-left at (x, 0): a leaf
    device, or an already-routed subcircuit (efuse_comp inside
    efuse_sense) kept unshifted in y so its supply rails stay at CS_RAIL_Y
    and merge with this cell's own rails. Returns the unit's port table
    (leaf reports' absolute pin positions) or None (subcircuit)."""
    if inst["kind"] == "x" and inst["master"] in b.netlist \
            and inst["master"] != "efuse":
        child = b.cells[inst["master"]]
        bb = child.bbox()
        dx = snap(round(x / DBU_UM)) - bb.left
        cell.insert(kdb.CellInstArray(child.cell_index(), kdb.Trans(dx, 0)))
        return {"iname": inst["name"], "inst": inst, "child": child,
                "rep": None, "pt": None, "w": bb.width() * DBU_UM,
                "top": bb.top * DBU_UM, "dx": dx * DBU_UM, "sub": inst["master"]}
    child = b.leaf(subckt, inst)
    rep = b.reports[f"{subckt}__{inst['name'][1:]}"]
    dx, dy = b.place(cell, child, x, 0.0)
    pt = {p["name"]: (gs(dx + p["x_um"]), gs(dy + p["y_um"]), p["width_um"])
          for p in rep["ports"]}
    bb = child.bbox()
    return {"iname": inst["name"], "inst": inst, "child": child, "rep": rep,
            "pt": pt, "w": bb.width() * DBU_UM, "top": bb.top * DBU_UM,
            "dx": None, "sub": None}


def _unit_pins(b, cell, u, net_pins, taps, label_at):
    """Stacks, ring bridges and taps for one row unit (see coldrv_cell:
    same conventions -- S lane 0.16 um west of its pin, G on it, D 0.16 um
    east; a source on its body net is merged into the guard ring with an
    M1 bridge and the ring leaves at TAP_S; a resistor's two heads are
    signals with lanes on the pad centres)."""
    inst, pt = u["inst"], u["pt"]
    if inst["master"] == "ppolyf_u":
        a, bb, bulk = inst["nodes"]
        assert bulk == "vss", f"{u['iname']}: resistor bulk off vss"
        for net, port in ((a, "R0_A"), (bb, "R0_B")):
            p = pt[port]
            b._stack(cell, p[0], p[1], p[0], via2=False)
            net_pins.setdefault(net, []).append((p[0], p[1], True))
            label_at.setdefault(net, (p[0], p[1]))
        return
    d, g, s, bb = inst["nodes"]
    if s == bb and bb in SUPPLY:
        b._m1_ring_bridge(cell, pt["U0_S"], pt["TAP_W"])
    else:
        assert s not in SUPPLY, f"{u['iname']}: supply source off its body"
        sp = pt["U0_S"]
        b._stack(cell, sp[0], sp[1], gs(sp[0] - CD_SHIFT), via2=False)
        net_pins.setdefault(s, []).append((gs(sp[0] - CD_SHIFT), sp[1], True))
        label_at.setdefault(s, (sp[0], sp[1]))
    for net, port, sh in ((d, "U0_D", CD_SHIFT), (g, "U0_G", 0.0)):
        assert net not in SUPPLY or port == "U0_G", \
            f"{u['iname']}: supply on {port}"
        p = pt[port]
        b._stack(cell, p[0], p[1], gs(p[0] + sh), via2=False)
        net_pins.setdefault(net, []).append((gs(p[0] + sh), p[1], True))
        label_at.setdefault(net, (p[0], p[1]))
    tp = pt["TAP_S"]
    taps.append((bb, tp[0], tp[1], True))
    label_at.setdefault(bb, (tp[0], tp[1]))


def _row_channels(b, cell, net_pins, taps, rail_x, y):
    """One M2 track per multi-pin net (stacked from y at CD_TRACK_PITCH),
    lanes from every pin up to its net's track, and the supply rails below
    the row with one lane down per ring tap. Returns (net -> track y)."""
    track_y = {}
    for net, pins in net_pins.items():
        if len(pins) < 2:
            continue
        track_y[net] = y
        xs = [p[0] for p in pins]
        b._box(cell, LS_M2, min(xs) - LS_W2 / 2, y - LS_W2 / 2, max(xs) + LS_W2 / 2, y + LS_W2 / 2)
        for lx, y0, pad in pins:
            b._box(cell, LS_M3, lx - LS_W3N / 2, y0 - M3_END, lx + LS_W3N / 2, y + M3_END)
            if pad:  # only where _stack left an M2 pad for the cut to land on
                b._cut(cell, LS_VIA2, lx, y0)
            b._cut(cell, LS_VIA2, lx, y)
        y = gs(y + CD_TRACK_PITCH)
    for net, tx, ty, pad in taps:
        ry = CS_RAIL_Y[net]
        if pad:
            b._stack(cell, tx, ty)
        else:
            b._cut(cell, LS_VIA2, tx, ty)
        b._box(cell, LS_M3, tx - LS_W3N / 2, ry - M3_END, tx + LS_W3N / 2, ty + M3_END)
        b._cut(cell, LS_VIA2, tx, ry)
        rail_x.setdefault(net, []).append(tx)
    for net, xs in rail_x.items():
        ry = CS_RAIL_Y[net]
        b._box(cell, LS_M2, min(xs) - LS_W2 / 2, ry - LS_W2 / 2, max(xs) + LS_W2 / 2, ry + LS_W2 / 2)
    return track_y


def _row_place_all(b, cell, subckt):
    """Place every instance of subckt in netlist order as one row,
    2 um between bounding boxes. Returns the units."""
    units, x = [], 0.0
    for inst in b.netlist[subckt]:
        u = _row_unit(b, cell, subckt, inst, x)
        units.append(u)
        x = gs(x + u["w"] + GAP_UM + 0.01)
    return units


def comp_cell(b, subckt):
    """efuse_comp on a one-row floorplan (netlist order west to east:
    XMt XM1 XM2 XMx1 XMx2 XMr1 XMr2), routed coldrv-style: via1 + M2 pad +
    via2 + M3 lane per signal pin, one M2 track per multi-pin net (tail,
    outp, outn, clkn) above the row, vss / vdd33 rails below it. The five
    signal-pin nets' lanes extend CS_EXPORT above the channel and their
    (x, y) tops are recorded in b.comp_export so efuse_sense can tie
    into them by overlapping M3; the rails are at CS_RAIL_Y so
    efuse_sense's own rails merge with them where they cross the instance.
    """
    expected = {"XMt", "XM1", "XM2", "XMx1", "XMx2", "XMr1", "XMr2"}
    assert {i["name"] for i in b.netlist[subckt]} == expected, \
        f"efuse_comp netlist changed: {sorted(i['name'] for i in b.netlist[subckt])}"
    cell = b.layout.create_cell(subckt)
    net_pins, taps, label_at, rail_x = {}, [], {}, {n: [] for n in CS_RAIL_Y}
    units = _row_place_all(b, cell, subckt)
    for u in units:
        _unit_pins(b, cell, u, net_pins, taps, label_at)
    track_y = _row_channels(b, cell, net_pins, taps, rail_x,
                            gs(max(u["top"] for u in units) + 1.5))
    # Pin exports: inp / inn are single-pin nets here (no track), so their
    # lanes and pin cuts are drawn now; clkn / outp / outn extend their
    # existing track lanes up past the channel.
    ytop = gs(max(track_y.values(), default=0.0) + CD_TRACK_PITCH + CS_EXPORT)
    export = {}
    for net, iname, port in (("inp", "XM1", "U0_G"), ("inn", "XM2", "U0_G")):
        u = next(u for u in units if u["iname"] == iname)
        lx, ypin = gs(u["pt"][port][0]), u["pt"][port][1]
        b._box(cell, LS_M3, lx - LS_W3N / 2, ypin - M3_END, lx + LS_W3N / 2, ytop + M3_END)
        b._cut(cell, LS_VIA2, lx, ypin)
        export[net] = (lx, ytop)
    for net in ("clkn", "outp", "outn"):
        lx = net_pins[net][0][0]
        b._box(cell, LS_M3, lx - LS_W3N / 2, track_y[net] - M3_END, lx + LS_W3N / 2, ytop + M3_END)
        export[net] = (lx, ytop)
    b.comp_export = export
    for net, (lx, ly) in label_at.items():
        b._label(cell, net, lx, ly)
    b.cells[subckt] = cell
    return cell


def sense_cell(b, subckt):
    """efuse_sense on a one-row floorplan: the twenty leaf instances
    (sixteen MOS, two ppolyf_u resistors, the W=60 select folded to six
    fingers) and the routed efuse_comp instance, all in netlist order,
    routed the same coldrv way (lanes up to one M2 track per multi-pin
    net above the row, supply rails below). The comparator is entered
    through shapes it already exposes: its five exported pin lanes are
    extended (overlapping M3) up to their nets' tracks in this cell's
    channel, and its rails merge with this cell's (same y, one long box).
    """
    expected = {"XMb", "XRb", "XMbs", "XMbp", "XMf", "XMrf", "XRref", "XMsw",
                "XMsel", "XMpca", "XMpcb", "XMnca", "XMncb", "Xcmp",
                "XMpqa", "XMpqb", "XMnqa", "XMnqb", "XMpba", "XMpbb",
                "XMnba", "XMnbb"}
    assert {i["name"] for i in b.netlist[subckt]} == expected, \
        f"efuse_sense netlist changed: {sorted(i['name'] for i in b.netlist[subckt])}"
    cell = b.layout.create_cell(subckt)
    net_pins, taps, label_at, rail_x = {}, [], {}, {n: [] for n in CS_RAIL_Y}
    units = _row_place_all(b, cell, subckt)
    cmpu = next(u for u in units if u["sub"] == "efuse_comp")
    # The comparator's rail span joins this cell's rails (same y), so they
    # merge where they cross the instance; its five exported pin lanes
    # become pin entries of their nets (no M2 pad at the tie-in point: the
    # lane is efuse_comp's own M3, extended up by the channel tracks).
    for net in CS_RAIL_Y:
        rail_x[net] += [cmpu["dx"] + 0.5, cmpu["dx"] + cmpu["w"] - 0.5]
    for u in units:
        if u["sub"] is None:
            _unit_pins(b, cell, u, net_pins, taps, label_at)
    nodes = cmpu["inst"]["nodes"]  # inp inn clkn outp outn vdd33 vss
    for net, pin in zip(nodes[:5], ("inp", "inn", "clkn", "outp", "outn")):
        lx, ytop = b.comp_export[pin]
        net_pins.setdefault(net, []).append((gs(cmpu["dx"] + lx), ytop, False))
    track_y = _row_channels(b, cell, net_pins, taps, rail_x,
                            gs(max(u["top"] for u in units) + 1.5))
    for net, (lx, ly) in label_at.items():
        b._label(cell, net, lx, ly)
    b.sa_ports = {"net_pins": net_pins, "label_at": label_at,
                  "track_y": track_y, "rail_x": rail_x}
    b.cells[subckt] = cell
    return cell
