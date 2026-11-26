#!/usr/bin/env python3
"""efuse_rowdrv / efuse_coldrv routing, built from efuse_ls and leaf devices.

rowdrv_cell and coldrv_cell, and the driver-specific tracks, taps and lanes
they draw (see layout/README.md, "efuse_rowdrv / efuse_coldrv routing").
efuse_comp and efuse_sense (route_sense.py) reuse the coldrv planes and
pitches: SUPPLY, CD_SHIFT and CD_TRACK_PITCH; efuse_otp_array's top routing
(route_array.py) taps the rails at CD_RAIL_Y.
"""

import klayout.db as kdb

from analog_core import (DBU_UM, GAP_UM, LS_M2, LS_M3, LS_PAD2, LS_VIA2, LS_W2,
                         LS_W3N, gs)
from route_ls import _ls_vstrip

# efuse_coldrv routing (see coldrv_cell and layout/README.md, "efuse_coldrv routing").
SUPPLY = ("vdd33", "vprog", "vss")
CD_SHIFT = 0.16  # S lane west / D lane east of the pin, so a device's three lanes sit 0.59 um apart
CD_TRACK_PITCH = 0.72  # M2 signal tracks above the device row (0.42 um wide)
CD_RAIL_Y = {"vss": -1.5, "vdd33": -2.22, "vprog": -2.94}  # M2 supply rails below the row
CD_LANE_PITCH = 0.72  # M3 lanes added beside the efuse_ls instance
CD_LS_RAIL_END = 16.0  # east end of efuse_ls's vss rail (ls_cell)


def rowdrv_cell(b, subckt):
    """efuse_rowdrv: the routed efuse_ls instance at the origin; the five
    ports are labels on the instance's own M1 pads (nothing else to draw)."""
    insts = b.netlist[subckt]
    assert [(i["master"], i["nodes"]) for i in insts] == [
        ("efuse_ls", ["row_sel", "wl", "vdd33", "vprog", "vss"])], \
        f"efuse_rowdrv netlist changed: {insts}"
    cell = b.layout.create_cell(subckt)
    cell.insert(kdb.CellInstArray(b.cells["efuse_ls"].cell_index(), kdb.Trans(0, 0)))
    lp = b.ls_ports
    for net, iname, port in (("row_sel", "XMni", "U0_G"), ("wl", "XMn2", "U0_D"),
                             ("vdd33", "XMpi", "TAP_W"), ("vprog", "XMp1", "TAP_S"),
                             ("vss", "XMn1", "TAP_S")):
        b._label(cell, net, lp[iname][port][0], lp[iname][port][1])
    b.cells[subckt] = cell
    return cell


def coldrv_cell(b, subckt):
    """efuse_coldrv: one routed efuse_ls at the origin and a row of leaf
    devices east of it (Mdrv as m=3 parallel units), all 13 nets drawn.

    Every signal pin gets via1 + an M2 pad + via2 and a vertical M3 lane
    (S lane CD_SHIFT west of its pin, G on it, D CD_SHIFT east, so a
    device's three lanes are 0.59 um apart) up to its net's M2 track in a
    channel above everything; the M3 lanes only meet M2 at their own via2.
    A source whose net is its body net is merged into the guard ring with
    the ls_cell M1 bridge; each ring then leaves at TAP_S, down an M3 lane
    to that supply's M2 rail below the row. efuse_ls is entered through
    shapes it already exposes: `in` by an M3 run west off its in strip,
    `out` by an M3 run east off its out vertical, vdd33 at the west end of
    its M2 stub, vprog by extending its M2 run east, vss by extending its
    rail east.
    """
    insts = b.netlist[subckt]
    cell = b.layout.create_cell(subckt)
    ls, lp = b.cells["efuse_ls"], b.ls_ports
    cell.insert(kdb.CellInstArray(ls.cell_index(), kdb.Trans(0, 0)))
    lsr, lst = ls.bbox().right * DBU_UM, ls.bbox().top * DBU_UM
    net_pins, taps = {}, []  # net -> [(lane_x, y0, has_m2_pad)]; [(net, x, y, with_pad)]
    label_at = {}

    # -- efuse_ls attachments
    inn = insts[[i["name"] for i in insts].index("Xls")]["nodes"]
    n_in, n_out, n_vdd, n_vprog, n_vss = inn
    assert (n_vdd, n_vprog, n_vss) == SUPPLY, "efuse_ls supply nets changed"
    gni, gpi = lp["XMni"]["U0_G"], lp["XMpi"]["U0_G"]
    y_in = gpi[1] - 0.3
    x_w = -1.7
    b._box(cell, LS_M3, x_w - LS_W3N / 2, y_in - LS_W3N / 2, gni[0], y_in + LS_W3N / 2)
    net_pins.setdefault(n_in, []).append((x_w, y_in, False))  # M3-to-M3 tie-in: no M2 below
    tw = lp["XMpi"]["TAP_W"]
    taps.append((n_vdd, -0.9, tw[1], False))
    dn2, dp2 = lp["XMn2"]["U0_D"], lp["XMp2"]["U0_D"]
    mx = dp2[0] + 0.06
    x_o = gs(lsr + 1.0)
    x_v = gs(x_o + CD_LANE_PITCH)
    y_out = 14.4
    b._box(cell, LS_M3, mx - LS_W3N / 2, y_out - LS_W3N / 2, x_o + LS_W3N / 2, y_out + LS_W3N / 2)
    net_pins.setdefault(n_out, []).append((x_o, y_out, False))  # M3-to-M3 tie-in: no M2 below
    ts1, ts2 = lp["XMp1"]["TAP_S"], lp["XMp2"]["TAP_S"]
    b._box(cell, LS_M2, ts2[0], ts1[1] - LS_W2 / 2, x_v + LS_PAD2 / 2, ts1[1] + LS_W2 / 2)
    taps.append((n_vprog, x_v, ts1[1], False))

    # -- leaf devices
    units = []  # (iname, inst, child, rep, x)
    x = gs(x_v + CD_LANE_PITCH + 1.5)
    for inst in insts:
        if inst["master"] == "efuse_ls":
            continue
        child = b.leaf(subckt, inst)
        rep = b.reports[f"{subckt}__{inst['name'][1:]}"]
        if inst["name"] == "XMdrv":
            b.add_program_diffusion_contacts(child, rep["ports"])
        for k in range(int(inst["params"].get("m", "1"))):
            units.append((inst["name"], inst, child, rep, x, k))
            x = gs(x + child.bbox().width() * DBU_UM + GAP_UM + 0.01)
    rail_x = {n: [] for n in SUPPLY}
    mdrv_straps = []
    for iname, inst, child, rep, col, k in units:
        dx, dy = b.place(cell, child, col, 0.0)
        pt = {p["name"]: (gs(dx + p["x_um"]), gs(dy + p["y_um"]), p["width_um"])
              for p in rep["ports"]}
        d, g, s, bb = inst["nodes"]
        if iname == "XMdrv":
            mdrv_straps.append((pt["TAP_S"][0], pt["U0_S"][1], pt["U0_D"][1]))
        if s == bb and bb in SUPPLY:
            b._m1_ring_bridge(cell, pt["U0_S"], pt["TAP_W"])
        else:
            assert s not in SUPPLY, f"{iname}: supply source off its body"
            sp = pt["U0_S"]
            b._stack(cell, sp[0], sp[1], gs(sp[0] - CD_SHIFT), via2=False)
            net_pins.setdefault(s, []).append((gs(sp[0] - CD_SHIFT), sp[1], True))
            label_at.setdefault(s, (sp[0], sp[1]))
        for net, port, sh in ((d, "U0_D", CD_SHIFT), (g, "U0_G", 0.0)):
            assert net not in SUPPLY, f"{iname}: supply on {port}"
            p = pt[port]
            b._stack(cell, p[0], p[1], gs(p[0] + sh), via2=False)
            net_pins.setdefault(net, []).append((gs(p[0] + sh), p[1], True))
            label_at.setdefault(net, (p[0], p[1]))
        tp = pt["TAP_S"]
        taps.append((bb, tp[0], tp[1], True))
        label_at.setdefault(bb, (tp[0], tp[1]))

    # -- tracks above, rails below
    y = gs(lst + 1.5)
    track_y = {}
    for net, pins in net_pins.items():
        if len(pins) < 2:
            continue
        track_y[net] = y
        xs = [p[0] for p in pins]
        b._box(cell, LS_M2, min(xs) - LS_W2 / 2, y - LS_W2 / 2, max(xs) + LS_W2 / 2, y + LS_W2 / 2)
        for lx, y0, pad in pins:
            # land0 only where _stack left an M2 pad for the cut to land on
            _ls_vstrip(b, cell, lx, y0, y, LS_W3N, land0=pad, land1=True)
            if pad:
                b._cut(cell, LS_VIA2, lx, y0)
            b._cut(cell, LS_VIA2, lx, y)
        y = gs(y + CD_TRACK_PITCH)
    for net, tx, ty, pad in taps:
        ry = CD_RAIL_Y[net]
        if pad:
            b._stack(cell, tx, ty)
        else:
            b._cut(cell, LS_VIA2, tx, ty)
        _ls_vstrip(b, cell, tx, ty, ry, LS_W3N, land0=True, land1=True)
        b._cut(cell, LS_VIA2, tx, ry)
        rail_x[net].append(tx)
    for net, xs in rail_x.items():
        lo = min(xs + ([CD_LS_RAIL_END - 1.0] if net == "vss" else []))
        ry = CD_RAIL_Y[net]
        b._box(cell, LS_M2, lo - LS_W2 / 2, ry - LS_W2 / 2, max(xs) + LS_W2 / 2, ry + LS_W2 / 2)
    for net, (lx, ly) in label_at.items():
        b._label(cell, net, lx, ly)
    b.cd_ports = {"net_pins": net_pins, "label_at": label_at,
                  "track_y": track_y, "rail_x": rail_x, "mdrv_straps": mdrv_straps}
    b.cells[subckt] = cell
    return cell
