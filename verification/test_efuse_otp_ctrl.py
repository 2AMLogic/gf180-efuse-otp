"""cocotb checks for rtl/efuse_otp_ctrl.v (spec section 2, decision 0004).

Configuration comes from the environment (set by runner.py):
EFUSE_ROWS, EFUSE_COLS, EFUSE_PULSE_N (expected program-pulse cycles),
EFUSE_SETTLE_N (expected sense-settle cycles).

Timing convention: inputs are driven and outputs sampled on the falling edge,
so a value driven at falling edge Fk is captured by rising edge Ek, and a
sample at Fk shows the state after Ek-1.  "E0" is the first rising edge with
rst low.  Arming completes on E1, so the first request that can be accepted is
the one presented at E2.
"""
import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, Timer
from cocotb.types import LogicArray

ROWS = int(os.environ["EFUSE_ROWS"])
COLS = int(os.environ["EFUSE_COLS"])
PULSE_N = int(os.environ["EFUSE_PULSE_N"])
SETTLE_N = int(os.environ["EFUSE_SETTLE_N"])
NBITS = ROWS * COLS


def val(sig):
    """Integer value of a signal; fails the test on X/Z (outputs must be clean)."""
    v = sig.value
    assert v.is_resolvable, f"{sig._name} is {v}, expected a resolved value"
    return int(v)


class Bench:
    def __init__(self, dut):
        self.dut = dut
        self.trace = []  # one dict per falling-edge sample

    async def start(self):
        d = self.dut
        d.rst.value = 1
        d.prog_en.value = 0
        d.rd_en.value = 0
        d.sense_in.value = 0
        d.addr.value = 0
        cocotb.start_soon(Clock(d.clk, 10, unit="ns").start())
        await FallingEdge(d.clk)

    def sample(self):
        d = self.dut
        s = dict(
            prog=val(d.prog_strobe),
            row=val(d.row_sel),
            col=val(d.col_sel),
            sense_en=val(d.sense_en),
            busy=val(d.busy),
            dout=val(d.dout),
        )
        self.trace.append(s)
        return s

    async def step(self, **drive):
        """Drive inputs now (a falling edge), advance to the next falling edge,
        sample outputs there."""
        for k, v in drive.items():
            getattr(self.dut, k).value = v
        await FallingEdge(self.dut.clk)
        return self.sample()

    async def reset(self, cycles=2):
        self.dut.rst.value = 1
        self.dut.prog_en.value = 0
        self.dut.rd_en.value = 0
        for _ in range(cycles):
            await self.step()

    async def release_and_arm(self):
        """Release reset and idle past arming; returns with the next edge being E3."""
        await self.step(rst=0)  # E0
        await self.step()       # E1 (arming completes)
        await self.step()       # E2
        # Caller drives for E3 onward; E2 passed idle.

    def strobe_runs(self):
        """Lengths of maximal runs of prog==1 in the trace."""
        runs, n = [], 0
        for s in self.trace:
            if s["prog"]:
                n += 1
            elif n:
                runs.append(n)
                n = 0
        if n:
            runs.append(n)
        return runs

    async def pulse(self, sig, **extra):
        """One-cycle rising-edge request on prog_en/rd_en, then deassert."""
        await self.step(**{sig: 1}, **extra)
        return await self.step(**{sig: 0})

    async def wait_idle(self, limit=None):
        limit = limit or (PULSE_N + SETTLE_N + 20)
        for _ in range(limit):
            if not val(self.dut.busy):
                return
            await self.step()
        raise AssertionError("busy never fell")


def onehot(n, i):
    return 1 << i


def split(addr):
    return addr // COLS, addr % COLS


async def armed_bench(dut):
    b = Bench(dut)
    await b.start()
    await b.reset()
    await b.release_and_arm()
    return b


# ---------------------------------------------------------------- reset / arming

@cocotb.test()
async def test_no_program_output_at_power_up(dut):
    """X-initialised inputs, reset held: program-side outputs are 0, never X."""
    d = dut
    d.rst.value = 1
    for s in (d.prog_en, d.rd_en, d.sense_in):
        s.value = LogicArray("X")
    d.addr.value = LogicArray("X" * len(d.addr))
    # Before any clock edge: reset gating alone must hold outputs inactive.
    await Timer(1, "ns")
    assert val(d.prog_strobe) == 0 and val(d.row_sel) == 0 and val(d.col_sel) == 0
    cocotb.start_soon(Clock(d.clk, 10, unit="ns").start())
    b = Bench(d)
    for _ in range(4):
        await FallingEdge(d.clk)
        s = b.sample()
        assert s["prog"] == 0 and s["row"] == 0 and s["col"] == 0 and s["busy"] == 0


@cocotb.test()
async def test_no_program_before_arming(dut):
    """prog_en pulsed during reset gives no program output, before or after
    release (the boundary cases E0/E1/E2 are in test_arming_boundary)."""
    b = Bench(dut)
    await b.start()
    await b.step(prog_en=1, addr=1)
    await b.step()
    await b.step(prog_en=0)
    await b.step(prog_en=1)  # still in reset
    await b.step(prog_en=0)
    for _ in range(PULSE_N + 10):
        await b.step(rst=0)
    assert b.strobe_runs() == [], b.strobe_runs()
    assert all(s["row"] == 0 and s["col"] == 0 and s["busy"] == 0 for s in b.trace)


@cocotb.test()
async def test_arming_boundary(dut):
    """Request presented at E1 is ignored (not armed); at E2 it is accepted."""
    for edge, expect in ((0, 0), (1, 0), (2, 1)):
        b = Bench(dut)
        await b.start()
        await b.reset()
        # Release reset; drive prog_en=1 for exactly edge number `edge` (E0..).
        for k in range(edge):
            await b.step(rst=0, prog_en=0)
        await b.step(rst=0, prog_en=1)
        await b.step(prog_en=0)
        for _ in range(PULSE_N + 12):
            await b.step()
        runs = b.strobe_runs()
        assert runs == ([PULSE_N] if expect else []), f"request at E{edge}: runs={runs}"


@cocotb.test()
async def test_enable_stuck_high_never_programs(dut):
    """prog_en high through reset and after release produces nothing until it
    has been seen low; then one rising edge gives exactly one pulse."""
    b = Bench(dut)
    await b.start()
    await b.step(prog_en=1)
    await b.step()
    await b.step(rst=0)
    for _ in range(PULSE_N + 20):
        await b.step()
    assert b.strobe_runs() == [], "stuck-high enable programmed"
    await b.step(prog_en=0)
    await b.step()
    await b.step(prog_en=1, addr=3)
    await b.step()  # held high through the whole pulse
    for _ in range(PULSE_N + 20):
        await b.step()
    assert b.strobe_runs() == [PULSE_N], b.strobe_runs()


@cocotb.test()
async def test_reset_mid_pulse(dut):
    """rst asserted mid-pulse drops every program output at once (before the
    next clock edge); after release nothing resumes and arming restarts."""
    b = await armed_bench(dut)
    await b.pulse("prog_en", addr=5 % NBITS)
    for _ in range(min(3, PULSE_N)):
        await b.step()
    assert val(dut.prog_strobe) == 1
    dut.rst.value = 1
    await Timer(1, "ns")  # no clock edge has happened yet
    assert val(dut.prog_strobe) == 0 and val(dut.row_sel) == 0
    assert val(dut.col_sel) == 0 and val(dut.busy) == 0
    await b.step()
    await b.step()
    n_before = len(b.strobe_runs())
    assert n_before == 1
    # Release and present a request at E1: still unarmed, must be ignored.
    await b.step(rst=0, prog_en=0)
    await b.step(prog_en=1)
    for _ in range(PULSE_N + 10):
        await b.step(prog_en=0)
    runs = b.strobe_runs()
    assert len(runs) == n_before, f"program output after mid-pulse reset: {runs}"
    assert runs[-1] < PULSE_N, "pulse was not cut short by reset"


# ---------------------------------------------------------------- program

@cocotb.test()
async def test_pulse_width_and_selects(dut):
    """Strobe is exactly PULSE_N cycles, with selects up one cycle before it and
    down with it, for first, last and middle addresses."""
    b = await armed_bench(dut)
    for addr in sorted({0, NBITS - 1, NBITS // 2 + 1}):
        start = len(b.trace)
        await b.pulse("prog_en", addr=addr)
        await b.wait_idle()
        await b.step()
        seg = b.trace[start:]
        r, c = split(addr)
        busy = [s for s in seg if s["busy"]]
        prog = [s for s in seg if s["prog"]]
        assert len(prog) == PULSE_N, f"addr {addr}: strobe {len(prog)} cycles, want {PULSE_N}"
        assert len(busy) == PULSE_N + 1, f"addr {addr}: busy {len(busy)} cycles"
        # selects are the latched address for the whole busy window, nothing else
        for s in seg:
            if s["busy"]:
                assert s["row"] == onehot(ROWS, r) and s["col"] == onehot(COLS, c), (addr, s)
            else:
                assert s["row"] == 0 and s["col"] == 0 and s["prog"] == 0
        # strobe only inside the busy window, after the select setup cycle
        first_busy = next(i for i, s in enumerate(seg) if s["busy"])
        assert not seg[first_busy]["prog"] and seg[first_busy + 1]["prog"]
    assert b.strobe_runs() == [PULSE_N] * 3


@cocotb.test()
async def test_address_change_while_busy(dut):
    """The accepting-edge address is latched; later changes do not move selects."""
    b = await armed_bench(dut)
    start = len(b.trace)
    await b.step(prog_en=1, addr=2)
    await b.step(prog_en=0, addr=NBITS - 1)
    for k in range(PULSE_N + 4):
        await b.step(addr=(k * 7 + 1) % NBITS)
    seg = b.trace[start:]
    r, c = split(2)
    assert b.strobe_runs() == [PULSE_N]
    for s in seg:
        if s["busy"]:
            assert s["row"] == onehot(ROWS, r) and s["col"] == onehot(COLS, c), s


@cocotb.test()
async def test_request_while_busy_ignored_and_back_to_back(dut):
    """A rising prog_en while busy is dropped; once idle, a new request gives a
    second full pulse."""
    b = await armed_bench(dut)
    await b.pulse("prog_en", addr=1)
    await b.step(prog_en=1)   # rises while busy
    await b.step(prog_en=0)
    await b.wait_idle()
    for _ in range(3):
        await b.step()
    assert b.strobe_runs() == [PULSE_N], "request during busy was not ignored"
    await b.pulse("prog_en", addr=2)
    await b.wait_idle()
    await b.step()
    assert b.strobe_runs() == [PULSE_N, PULSE_N]


@cocotb.test()
async def test_busy_idle_low(dut):
    b = await armed_bench(dut)
    for _ in range(5):
        s = await b.step()
        assert s["busy"] == 0 and s["prog"] == 0 and s["sense_en"] == 0


# ---------------------------------------------------------------- read

@cocotb.test()
async def test_read_settle_and_sample(dut):
    """sense_en is high for exactly SETTLE_N cycles; dout takes sense_in as
    seen at the last settle edge (not earlier, not later)."""
    b = await armed_bench(dut)
    for want in (1, 0, 1):
        start = len(b.trace)
        addr = 6 % NBITS
        s = await b.step(rd_en=1, addr=addr)  # sample after the accepting edge
        k = 0
        while s["sense_en"]:
            # Sample k is settle cycle k; the value driven now is captured at
            # its closing edge.  Present `want` only at the final settle edge,
            # the complement before.
            last = (k == SETTLE_N - 1)
            s = await b.step(rd_en=0, sense_in=(want if last else 1 - want))
            k += 1
        await b.step()
        seg = b.trace[start:]
        assert sum(x["sense_en"] for x in seg) == SETTLE_N, "settle count"
        assert seg[-1]["dout"] == want, f"dout {seg[-1]['dout']} want {want}"
        assert all(x["prog"] == 0 for x in seg), "read produced a program strobe"
        r, c = split(addr)
        assert all(x["row"] == onehot(ROWS, r) for x in seg if x["busy"])
        assert sum(x["busy"] for x in seg) == SETTLE_N


@cocotb.test()
async def test_read_works_before_arming(dut):
    b = Bench(dut)
    await b.start()
    await b.reset()
    await b.step(rst=0)
    await b.step(rd_en=1, sense_in=1)
    for _ in range(SETTLE_N + 3):
        await b.step(rd_en=0)
    assert sum(x["sense_en"] for x in b.trace) == SETTLE_N
    assert b.trace[-1]["dout"] == 1 and b.strobe_runs() == []


@cocotb.test()
async def test_read_has_priority_over_program(dut):
    """prog_en and rd_en rising together: the read runs, the program is dropped."""
    b = await armed_bench(dut)
    await b.step(prog_en=1, rd_en=1, addr=4)
    await b.step(prog_en=0, rd_en=0)
    for _ in range(PULSE_N + SETTLE_N + 10):
        await b.step()
    assert b.strobe_runs() == []
    assert sum(x["sense_en"] for x in b.trace) == SETTLE_N
