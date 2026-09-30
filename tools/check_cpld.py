"""Prove that the r5 ATF1502AS (code/pld/cpld/ic2_glue.pld) does what the three r4 chips did.

Decoder and glue: the reference is not the r4 equations but the r4 JEDEC fuse maps, run by gal.py:
IC2 decodes the address, its /IO, /ROM, /DUASEL and BANKSEL feed IC5, as on the r4 board. The CPLD
side is run from its CUPL source by cupl.py, with the reset counter finished. Every combination of
A1..A15, PHI2, R/W and /DUADTACK is compared (2^18 cases); A0, /VP, /ML and /IRQ reach the GALs but
not their equations, so they are varied too, to show they really are don't-cares. Tri-state
outputs compare as 'driven low' vs 'released'.

Reset (was the 555): /RESET must be held from power-up for exactly 2^18 PHI2 clocks, released after
that, pulled again while S1 is down, bounce included, and released 2^18 clocks after S1 lets go.

  python tools/check_cpld.py
"""
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLD = os.path.join(HERE, '..', 'code', 'pld')
sys.path.insert(0, HERE)
import cupl  # noqa: E402
import gal   # noqa: E402


def load_gal(path):
    text = open(path + '.pld').read()
    return gal.pins(text), gal.Gal22V10(gal.jedec(open(path + '.jed').read()))


ic2_pins, ic2 = load_gal(os.path.join(PLD, 'address_decoder', 'ic2_address_decoder'))
ic5_pins, ic5 = load_gal(os.path.join(PLD, 'glue', 'ic5_glue_logic'))
cpld = cupl.Device(open(os.path.join(PLD, 'cpld', 'ic2_glue.pld')).read())
ic2_num = {n: p for p, n in ic2_pins.items()}
ic5_num = {n: p for p, n in ic5_pins.items()}

# r4 board net -> (GAL, pin) that drives it; r5 pin name of the same net
OUTPUTS = {
    'LOWRAM_N': (ic2, ic2_num['LOWRAM']),
    'BANKRAM_N': (ic2, ic2_num['BANKRAM']),
    'DUASEL_N': (ic2, ic2_num['DUASEL']),
    'ROMOE_N': (ic5, ic5_num['ROMOE1']),       # the net on the r4 board; ROMOE2 is unconnected
    'RD_N': (ic5, ic5_num['RD']),
    'WR_N': (ic5, ic5_num['WR']),
    'BANKCLK': (ic5, ic5_num['BANKCLK']),
    'RDY': (ic5, ic5_num['RDY']),
}
assert set(OUTPUTS) | {'RESET_N'} == {n for n in cpld.pins.values() if n not in cpld.inputs}, 'pin list drifted'
RESET_CLOCKS = 1 << 18


def r4(addr, phi2, rw, dtack_n, extra):
    a = {ic2_num[f'A{i}']: addr >> i & 1 for i in range(16)}
    o2 = ic2.outputs(a)
    a.update({p: v for p, v in o2.items() if v is not None})   # /DUASEL uses /IO fed back from its pin
    o2 = ic2.outputs(a)
    lv = {ic5_num['CLK']: phi2, ic5_num['DUADT']: dtack_n, ic5_num['RnW']: rw, ic5_num['HWRST']: 0,
          ic5_num['DUASEL']: o2[ic2_num['DUASEL']], ic5_num['BANKSEL']: o2[ic2_num['BANKSEL']],
          ic5_num['ROM']: o2[ic2_num['ROM']], ic5_num['IO']: o2[ic2_num['IO']],
          ic5_num['VP']: extra & 1, ic5_num['ML']: extra >> 1 & 1, ic5_num['IRQ']: extra >> 2 & 1}
    o5 = ic5.outputs(lv)
    return {name: (o2 if chip is ic2 else o5)[pin] for name, (chip, pin) in OUTPUTS.items()}


DONE = dict(cpld.reset_state(), RC18=1)       # reset counter finished


def r5(addr, phi2, rw, dtack_n):
    p = {f'A{i}': addr >> i & 1 for i in range(1, 16)}
    p.update(PHI2=phi2, RW=rw, DUADTACK_N=dtack_n, RSTBTN_N=1)
    out = cpld.outputs(p, dict(DONE))
    assert out.pop('RESET_N') is None, 'reset held after the count'
    return out


def reset_run():
    """Clock the counter, button up unless told otherwise; return how long /RESET stayed low."""
    p = {f'A{i}': 1 for i in range(1, 16)}
    p.update(RW=1, DUADTACK_N=1, RSTBTN_N=1, PHI2=0)
    q = cpld.reset_state()                             # the ATF1502AS clears at power-up

    def held(q):
        return cpld.outputs(p, q)['RESET_N'] == 0

    def clocks_until_release(q, limit):
        n = 0
        while held(q):
            assert n <= limit, 'reset never ends'
            q = cpld.clock_edge(p, q); n += 1
        return n, q

    n, q = clocks_until_release(q, RESET_CLOCKS + 10)
    assert n == RESET_CLOCKS, f'power-up reset lasted {n} clocks'
    for _ in range(1000):                              # and it stays released
        q = cpld.clock_edge(p, q); assert not held(q)
    for level in (0, 1, 0, 1, 0):                      # S1 goes down, bouncing
        p['RSTBTN_N'] = level
        assert held(q) if level == 0 else True
        for _ in range(37):
            q = cpld.clock_edge(p, q)
        assert held(q), 'reset released while the button bounces'
    p['RSTBTN_N'] = 1
    n, q = clocks_until_release(q, RESET_CLOCKS + 10)
    assert n == RESET_CLOCKS, f'button reset lasted {n} clocks after release'
    return n


def main():
    cases = bad = 0
    for addr2, phi2, rw, dtack_n in itertools.product(range(1 << 15), (0, 1), (0, 1), (0, 1)):
        extra = (addr2 * 7 + phi2 * 3 + rw * 5 + dtack_n) & 15   # A0, /VP, /ML, /IRQ: cheap spread
        addr = addr2 << 1 | extra & 1
        want = r4(addr, phi2, rw, dtack_n, extra >> 1)
        got = r5(addr, phi2, rw, dtack_n)
        cases += 1
        if want != got:
            bad += 1
            if bad <= 10:
                diff = {k: (want[k], got[k]) for k in want if want[k] != got[k]}
                print(f'MISMATCH ${addr:04X} phi2={phi2} rw={rw} dtack_n={dtack_n}: '
                      f'(r4, r5) = {diff}')
    print(f'decoder + glue: {cases} cases, {bad} mismatches against the r4 fuses')
    if bad:
        sys.exit(1)
    n = reset_run()
    print(f'reset: {n} PHI2 clocks after power-up and after S1 '
          f'({n / 14e6 * 1e3:.0f} ms at 14 MHz, {n / 10e6 * 1e3:.0f} ms at 10 MHz), bounce holds it')


if __name__ == '__main__':
    main()
