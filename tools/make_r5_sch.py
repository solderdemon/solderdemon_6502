"""Derive the r5 schematic from the r4 one in git.

r5 changes three things and leaves every other symbol, wire and label of r4 where it was:
  - IC2 + IC5 (two ATF22V10C) and IC4 (the NE555 reset timer, with C19, C20 and R9) become one
    ATF1502AS-10JU44 in a PLCC-44 socket, still called IC2 (code/firmware/pld/cpld/ic2_glue.pld);
  - J8, a 10-pin JTAG header, programs it in circuit;
  - S1 now pulls the CPLD's reset input low directly, with R8 (3K3, like every other pull-up) as
    its pull-up.

The input is always the r4 file at BASE, so the script can be rerun at will and gives the same
bytes every time (new UUIDs are uuid5 of the sheet UUID and a name).

How the removal works: wires are grouped into connected pieces. A piece that touches a pin of a
removed part goes, with its labels, junctions and no-connect flags. A surviving pin that was on
such a piece gets a global label with its net's name instead (NEW_NET overrides that name), and a
power symbol on it goes too. So nothing that stays loses its connection, and nothing that went
leaves a stub behind.

The result is the first SolderDemon revision, SolderDemon 6502 r1: the project is renamed to
solderdemon_6502 and the title block carries the SolderDemon identity (TITLE_BLOCK), with the
upstream notice kept in one comment line (CERN OHL 3.1 and 3.4b). The symbol library keeps its rosco_6502 name.

    python tools/make_r5_sch.py     # writes design/solderdemon_6502.kicad_sch and .pdf, rosco_6502.kicad_sym
"""
from pathlib import Path
import math, os, re, subprocess, sys, uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sexpr import parse, props, quote  # noqa: E402
import cupl  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCH_BASE = 'design/kicad/rosco_6502.kicad_sch'           # r4 in git, under its upstream name
SCH = 'design/solderdemon_6502.kicad_sch'
PROJECT_OLD, PROJECT = 'rosco_6502', 'solderdemon_6502'
LIB_BASE = 'design/kicad/rosco_6502.kicad_sym'
LIB = 'design/rosco_6502.kicad_sym'
BASE = 'febedf81d62ee84a51998f37c9de908616646e20'                                         # r4, as last committed
TITLE_BLOCK = '''(title_block
    (title "SolderDemon 6502")
    (date "2026-09-30")
    (rev "r1")
    (company "SolderDemon")
    (comment 1 "Copyright (c)2026 SolderDemon")
    (comment 2 "Open Source Hardware (CERN OHL v1.2)")
    (comment 3 "Modified 2026-09-30 from rosco_6502 r4, (c)2022-2023 Ross Bamford & Contributors")
  )'''

REMOVE = {'IC2', 'IC4', 'IC5', 'C19', 'C20', 'R9'}
NEW_NET = {('S1', '3'): '~{RSTBTN}', ('R8', '1'): '~{RSTBTN}', ('S1', '1'): 'GND'}
NEW_VALUE = {'R8': '3K3'}

# CPLD signal (as named in ic2_glue.pld) -> schematic net
CPLD_NET = {
    'PHI2': 'CLK', 'RSTBTN_N': '~{RSTBTN}', 'RW': 'R/~{W}', 'DUADTACK_N': '~{DUADTACK}',
    'RESET_N': '~{RESET}', 'RDY': 'RDY', 'DUASEL_N': '~{DUASEL}', 'LOWRAM_N': '~{LOWRAM}',
    'BANKRAM_N': '~{BANKRAM}', 'ROMOE_N': '~{ROMOE}', 'RD_N': '~{RD}', 'WR_N': '~{WR}',
    'BANKCLK': 'BANKCLK', **{f'A{i}': f'A{i}' for i in range(1, 16)},
}
JTAG = {7: 'TDI', 13: 'TMS', 32: 'TCK', 38: 'TDO'}
VCC_PINS, GND_PINS = (3, 15, 23, 35), (10, 22, 30, 42)
# Atmel ATDH1150USB / Altera ByteBlaster 10-pin pinout
J8_PINS = {1: 'TCK', 2: 'GND', 3: 'TDO', 4: 'VCC', 5: 'TMS', 6: None, 7: None, 8: None, 9: 'TDI', 10: 'GND'}

IC2_AT, J8_AT = (256.54, 149.86), (152.4, 130.81)
G = 2.54
NL = chr(10)


def git_show(path):
    return subprocess.run(['git', 'show', f'{BASE}:{path}'], cwd=ROOT, check=True,
                          capture_output=True).stdout.decode('utf-8')


def r4_netlist():
    """(ref, pin) -> net name, from KiCad's own netlist of the r4 schematic."""
    import tempfile, xml.etree.ElementTree as ET
    with tempfile.TemporaryDirectory() as d:
        for f in ('rosco_6502.kicad_sch', 'rosco_6502.kicad_pro', 'sym-lib-table', 'rosco_6502.kicad_sym',
                  '65xx.lib', '65xx.dcm'):
            (Path(d) / f).write_bytes(subprocess.run(['git', 'show', f'{BASE}:design/kicad/{f}'], cwd=ROOT,
                                                     check=True, capture_output=True).stdout)
        out = Path(d) / 'net.xml'
        subprocess.run([CLI, 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(out),
                        str(Path(d) / 'rosco_6502.kicad_sch')], check=True, capture_output=True)
        root = ET.parse(out).getroot()
    return {(n.get('ref'), n.get('pin')): net.get('name') for net in root.iter('net') for n in net.iter('node')}


CLI = os.environ.get('KICAD_CLI', 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')


# ---- geometry ------------------------------------------------------------------------------

def rnd(p):
    return (round(p[0], 3), round(p[1], 3))


def transform(sym):
    at = sym.find('at')
    X, Y, rot = float(at[1]), float(at[2]), int(float(at[3])) if len(at) > 3 else 0
    mir = sym.value('mirror')
    c, s = round(math.cos(math.radians(rot))), round(math.sin(math.radians(rot)))

    def f(px, py, move=True):
        x, y = px, -py                                   # library y is up, sheet y is down
        if mir == 'x': y = -y
        if mir == 'y': x = -x
        return (X * move + x * c + y * s, Y * move - x * s + y * c)
    return f


def lib_pins(lib):
    out = []
    for u in lib.findall('symbol'):
        unit = int(re.search(r'_(\d+)_\d+$', u[1]).group(1))
        for p in u.findall('pin'):
            at = p.find('at')
            out.append((unit, p.find('number')[1], float(at[1]), float(at[2]), float(at[3])))
    return out


def on_segment(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    if abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) > 1e-6: return False
    return min(x1, x2) - 1e-6 <= x <= max(x1, x2) + 1e-6 and min(y1, y2) - 1e-6 <= y <= max(y1, y2) + 1e-6


# ---- text snippets -------------------------------------------------------------------------

class Uid:
    def __init__(self, ns): self.ns = uuid.UUID(ns)
    def __call__(self, name): return str(uuid.uuid5(self.ns, name))


def label(uid, net, xy, direction, shape='passive'):
    """Global label whose flag points away from the pin, in `direction` (dx, dy) on the sheet."""
    angle = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[direction]
    just = 'left' if angle in (0, 90) else 'right'
    x, y = xy
    return (f'  (global_label {quote(net)} (shape {shape}) (at {x:g} {y:g} {angle}) (fields_autoplaced)\n'
            f'    (effects (font (size 1.27 1.27)) (justify {just}))\n'
            f'    (uuid {uid(f"label {net} {x:g} {y:g}")})\n'
            f'    (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {x:g} {y:g} 0)\n'
            f'      (effects (font (size 1.27 1.27)) (justify {just}) hide)\n'
            f'    )\n  )\n')


def no_connect(uid, xy):
    return f'  (no_connect (at {xy[0]:g} {xy[1]:g}) (uuid {uid(f"nc {xy[0]:g} {xy[1]:g}")}))\n'


def text_note(uid, s, xy):
    return (f'  (text {quote(s)} (at {xy[0]:g} {xy[1]:g} 0)\n'
            f'    (effects (font (size 1.27 1.27)) (justify left bottom))\n'
            f'    (uuid {uid("text " + s)})\n  )\n')


def pin_text(kind, x, y, angle, name, num, length=G):
    return (f'        (pin {kind} line (at {x:g} {y:g} {angle}) (length {length:g})\n'
            f'          (name {quote(name)} (effects (font (size 1.27 1.27))))\n'
            f'          (number {quote(str(num))} (effects (font (size 1.27 1.27))))\n        )\n')


def lib_symbol(name, ref, value, body, pins, hide_names=False, fp_filter=''):
    """body: (x1, y1, x2, y2) rectangle; pins: list of pin_text() strings."""
    x1, y1, x2, y2 = body
    names = ' hide' if hide_names else ''
    return (f'    (symbol {quote(name)} (pin_names (offset 1.016){names}) (in_bom yes) (on_board yes)\n'
            f'      (property "Reference" {quote(ref)} (at {x1:g} {y1 + 1.27:g} 0)\n'
            f'        (effects (font (size 1.27 1.27)) (justify left))\n      )\n'
            f'      (property "Value" {quote(value)} (at {x1:g} {y2 - 1.27:g} 0)\n'
            f'        (effects (font (size 1.27 1.27)) (justify left))\n      )\n'
            f'      (property "Footprint" "" (at 0 0 0)\n        (effects (font (size 1.27 1.27)) hide)\n      )\n'
            f'      (property "Datasheet" "" (at 0 0 0)\n        (effects (font (size 1.27 1.27)) hide)\n      )\n'
            f'      (property "ki_fp_filters" {quote(fp_filter)} (at 0 0 0)\n'
            f'        (effects (font (size 1.27 1.27)) hide)\n      )\n'
            f'      (symbol {quote(name.split(":")[-1] + "_0_1")}\n'
            f'        (rectangle (start {x1:g} {y1:g}) (end {x2:g} {y2:g})\n'
            f'          (stroke (width 0.254) (type default))\n          (fill (type background))\n        )\n'
            f'      )\n'
            f'      (symbol {quote(name.split(":")[-1] + "_1_1")}\n' + ''.join(pins) + '      )\n    )\n')


def instance(uid, sheet, lib_id, ref, value, footprint, xy, pins, fields, datasheet=''):
    """fields: (dx, dy) of the reference; the value goes one text line below it."""
    x, y = xy
    rx, ry = x + fields[0], y + fields[1]
    pin_lines = ''.join(f'    (pin {quote(str(p))} (uuid {uid(f"{ref} pin {p}")}))\n' for p in pins)
    return (f'  (symbol (lib_id {quote(lib_id)}) (at {x:g} {y:g} 0) (unit 1)\n'
            f'    (in_bom yes) (on_board yes) (dnp no)\n'
            f'    (uuid {uid(f"symbol {ref}")})\n'
            f'    (property "Reference" {quote(ref)} (at {rx:g} {ry:g} 0)\n'
            f'      (effects (font (size 1.27 1.27)) (justify left))\n    )\n'
            f'    (property "Value" {quote(value)} (at {rx:g} {ry + G:g} 0)\n'
            f'      (effects (font (size 1.27 1.27)) (justify left))\n    )\n'
            f'    (property "Footprint" {quote(footprint)} (at {x:g} {y:g} 0)\n'
            f'      (effects (font (size 1.27 1.27)) hide)\n    )\n'
            f'    (property "Datasheet" {quote(datasheet)} (at {x:g} {y:g} 0)\n'
            f'      (effects (font (size 1.27 1.27)) hide)\n    )\n' + pin_lines +
            f'    (instances\n      (project "rosco_6502"\n        (path "/{sheet}"\n'
            f'          (reference {quote(ref)}) (unit 1)\n        )\n      )\n    )\n  )\n')


# ---- the new parts -------------------------------------------------------------------------

def cpld_pins():
    """pin -> (signal, pin type, side). The pinout is read from the .pld, nowhere else."""
    dev = cupl.Device((ROOT / 'code/firmware/pld/cpld/ic2_glue.pld').read_text())
    out = {}
    for pin, name in dev.pins.items():
        kind = 'input' if name in dev.inputs else 'output'
        if name in ('RESET_N', 'RDY'): kind = 'open_collector'
        out[pin] = (name, kind)
    for pin, name in JTAG.items():
        out[pin] = (name, 'output' if name == 'TDO' else 'input')
    for pin in VCC_PINS: out[pin] = ('VCC', 'power_in')
    for pin in GND_PINS: out[pin] = ('GND', 'power_in')
    for pin in range(1, 45):
        out.setdefault(pin, (f'IO{pin}', 'bidirectional'))    # spare I/O, flagged no-connect
    return out


def cpld_layout(pins):
    """Symbol-local pin positions: inputs left, outputs and spares right, power top and bottom."""
    left = [p for p, (n, k) in pins.items() if k == 'input']
    order = [f'A{i}' for i in range(1, 16)] + ['PHI2', 'RW', 'RSTBTN_N', 'DUADTACK_N', 'TDI', 'TMS', 'TCK']
    left.sort(key=lambda p: order.index(pins[p][0]))
    right_order = ['RESET_N', 'RDY', 'DUASEL_N', 'LOWRAM_N', 'BANKRAM_N', 'ROMOE_N', 'RD_N', 'WR_N',
                   'BANKCLK', 'TDO']
    right = sorted((p for p, (n, k) in pins.items() if n in right_order), key=lambda p: right_order.index(pins[p][0]))
    right += sorted(p for p, (n, k) in pins.items() if k == 'bidirectional')
    top = (25.4, 0)
    pos = {}
    for i, p in enumerate(left):
        pos[p] = (-17.78, top[0] - i * G, 0)
    for i, p in enumerate(right):
        pos[p] = (17.78, top[0] - i * G - (G if i >= len(right_order) else 0), 180)
    for i, p in enumerate(VCC_PINS):
        pos[p] = ((i - 2) * G, 35.56, 270)
    for i, p in enumerate(GND_PINS):
        pos[p] = ((i - 2) * G, -35.56, 90)
    return pos


def cpld_display_name(name):
    return {'PHI2': 'PHI2/GCLK1', 'RSTBTN_N': '~{RSTBTN}/GCLR', 'RW': 'R/~{W}/OE2', 'DUADTACK_N': '~{DUADTACK}/OE1',
            'RESET_N': '~{RESET}', 'DUASEL_N': '~{DUASEL}', 'LOWRAM_N': '~{LOWRAM}', 'BANKRAM_N': '~{BANKRAM}',
            'ROMOE_N': '~{ROMOE}', 'RD_N': '~{RD}', 'WR_N': '~{WR}'}.get(name, name)


def build():
    text = git_show(SCH_BASE)
    root = parse(text)
    sheet = root.value('uuid')
    uid = Uid(sheet)
    nets = r4_netlist()

    libs = {s[1]: s for s in root.find('lib_symbols').findall('symbol')}
    symbols = root.findall('symbol')
    ref_of = {id(s): props(s)['Reference'] for s in symbols}

    # every pin on the sheet: (xy) -> [(symbol, number, outward direction)]
    pins_at = {}
    for s in symbols:
        f, unit = transform(s), int(s.value('unit'))
        for u, num, px, py, ang in lib_pins(libs[s.value('lib_id')]):
            if u not in (0, unit): continue
            xy = rnd(f(px, py))
            dx, dy = f(math.cos(math.radians(ang)), math.sin(math.radians(ang)), move=False)
            pins_at.setdefault(xy, []).append((s, num, (-round(dx), -round(dy))))

    # connected pieces of wire
    wires = root.findall('wire')
    ends = [tuple(rnd((float(xy[1]), float(xy[2]))) for xy in w.find('pts').findall('xy')) for w in wires]
    parent = list(range(len(wires)))

    def top(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i, (a, b) in enumerate(ends):
        for j, (c, d) in enumerate(ends[:i]):
            if a in (c, d) or b in (c, d) or on_segment(a, c, d) or on_segment(b, c, d) \
                    or on_segment(c, a, b) or on_segment(d, a, b):
                parent[top(i)] = top(j)
    pieces = {}
    for i in range(len(wires)): pieces.setdefault(top(i), []).append(i)

    def touching(piece, xy):
        return any(xy in ends[i] or on_segment(xy, *ends[i]) for i in piece)

    point_items = [n for n in root if hasattr(n, 'head') and n.head in ('global_label', 'label', 'junction', 'no_connect')]

    def at(n):
        a = n.find('at'); return rnd((float(a[1]), float(a[2])))

    cut, add = set(), []                                  # spans to delete, text to insert
    orphan_pins = []                                      # surviving pins that lost their wire
    for piece in pieces.values():
        on = [(xy, s, num, d) for xy, lst in pins_at.items() if touching(piece, xy) for s, num, d in lst]
        if not any(ref_of[id(s)] in REMOVE for _, s, _, _ in on): continue
        cut.update(wires[i].span for i in piece)
        cut.update(n.span for n in point_items if touching(piece, at(n)))
        for xy, s, num, d in on:
            ref = ref_of[id(s)]
            if ref in REMOVE: continue
            if ref.startswith('#'): cut.add(s.span)      # power symbol hanging off the piece
            else: orphan_pins.append((ref, num, xy, d))

    # labels and flags sitting straight on a removed pin
    for n in point_items:
        if any(ref_of[id(s)] in REMOVE for s, _, _ in pins_at.get(at(n), [])):
            cut.add(n.span)
    for s in symbols:
        if ref_of[id(s)] in REMOVE: cut.add(s.span)
    for n in root.findall('text'):
        if n[1].endswith('.pld'): cut.add(n.span)

    for ref, num, xy, d in sorted(orphan_pins):
        net = NEW_NET.get((ref, num), nets.get((ref, num)))
        if net is None or net.startswith('unconnected-'):
            add.append(no_connect(uid, xy))
        else:
            add.append(label(uid, net, xy, d))

    # ---- IC2: ATF1502AS ----
    cp = cpld_pins()
    pos = cpld_layout(cp)
    pin_txt = [pin_text(k, *pos[p], cpld_display_name(n), p) for p, (n, k) in sorted(cp.items())]
    body = (-15.24, 33.02, 15.24, -33.02)
    cpld_lib = lib_symbol('rosco_6502:ATF1502AS-10JU44', 'IC', 'ATF1502AS-10JU44', body, pin_txt,
                          fp_filter='PLCC*44*')
    add.append(instance(uid, sheet, 'rosco_6502:ATF1502AS-10JU44', 'IC2', 'ATF1502AS-10JU44',
                        'Package_LCC:PLCC-44_THT-Socket', IC2_AT, sorted(cp), (7.62, -40.64),
                        'https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-0995-CPLD-ATF1502AS(L)-Datasheet.pdf'))
    X, Y = IC2_AT
    for p, (n, k) in sorted(cp.items()):
        lx, ly, ang = pos[p]
        xy = rnd((X + lx, Y - ly))
        d = {0: (-1, 0), 180: (1, 0), 270: (0, -1), 90: (0, 1)}[int(ang)]
        if k == 'bidirectional':
            add.append(no_connect(uid, xy)); continue
        net = CPLD_NET.get(n, n)
        shape = {'input': 'input', 'output': 'output', 'open_collector': 'tri_state'}.get(k, 'passive')
        add.append(label(uid, net, xy, d, shape))
    add.append(text_note(uid, 'code/firmware/pld/cpld/ic2_glue.pld', (X - 15.24, Y + 45.72)))

    # ---- J8: JTAG ----
    jp = []
    for n in range(1, 11):
        x = -5.08 if n % 2 else 7.62
        y = 5.08 - (n - 1) // 2 * G
        jp.append(pin_text('passive', x, y, 0 if n % 2 else 180, f'Pin_{n}', n, 3.81))
    j8_lib = lib_symbol('Connector_Generic:Conn_02x05_Odd_Even', 'J', 'Conn_02x05_Odd_Even',
                        (-1.27, 6.35, 3.81, -6.35), jp, hide_names=True, fp_filter='Connector*:*_2x??_*')
    add.append(instance(uid, sheet, 'Connector_Generic:Conn_02x05_Odd_Even', 'J8', 'JTAG',
                        'Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical', J8_AT, range(1, 11),
                        (-5.08, -10.16)))
    X, Y = J8_AT
    for n, net in J8_PINS.items():
        x = X - 5.08 if n % 2 else X + 7.62
        y = Y - 5.08 + (n - 1) // 2 * G
        xy = rnd((x, y))
        if net is None: add.append(no_connect(uid, xy))
        else: add.append(label(uid, net, xy, (-1, 0) if n % 2 else (1, 0)))
    add.append(text_note(uid, 'J8: IC2 JTAG (ATDH1150USB)', (X - 12.7, Y + 11.43)))

    # ---- splice ----
    lib_end = root.find('lib_symbols').span[1] - 1          # just before the closing paren
    edits = [(s, e, '') for s, e in cut]
    edits.append((lib_end, lib_end, cpld_lib + j8_lib))
    tail = root.find('sheet_instances').span[0]
    edits.append((tail, tail, ''.join(add) + '\n  '))
    for ref, value in NEW_VALUE.items():
        s = next(s for s in symbols if ref_of[id(s)] == ref)
        v = next(p for p in s.findall('property') if p[1] == 'Value')
        a, b = v.span
        edits.append((a, b, text[a:b].replace(quote(v[2]), quote(value), 1)))
    tb = root.find('title_block')
    a, b = tb.span
    edits.append((a, b, TITLE_BLOCK))

    out = text
    for s, e, new in sorted(edits, key=lambda x: x[0], reverse=True):
        if e > s and s > 0 and out[s - 2:s] == '  ' and out[e:e + 1] == '\n' and not new:
            s, e = s - 2, e + 1                             # take the item's own line with it
        out = out[:s] + new + out[e:]
    out = re.sub(r'\n{3,}', '\n\n', out)
    out = out.replace(f'(project "{PROJECT_OLD}"', f'(project "{PROJECT}"')
    (ROOT / SCH).write_text(out, encoding='utf-8', newline='\n')
    # the same symbol in the project library, so the schematic and the library agree
    lib = git_show(LIB_BASE)
    sym = cpld_lib.replace('"rosco_6502:ATF1502AS-10JU44"', '"ATF1502AS-10JU44"')
    sym = ''.join(line[2:] + NL for line in sym.splitlines())
    end = lib.rstrip().rindex(')')
    (ROOT / LIB).write_text(lib[:end] + sym + lib[end:], encoding='utf-8', newline=NL)

    pdf = ROOT / 'manufacturing/solderdemon_6502-schematic.pdf'
    pdf.parent.mkdir(exist_ok=True)
    subprocess.run([CLI, 'sch', 'export', 'pdf', '-o', str(pdf), str(ROOT / SCH)],
                   check=True, capture_output=True)

    print(f'removed {len(cut)} items, added {len(add)}; orphaned pins relabelled: '
          + ', '.join(f'{r}.{n}' for r, n, _, _ in sorted(orphan_pins)))
    return cpld_lib


if __name__ == '__main__':
    build()
