"""Derive the r5 board from the r4 one in git, up to the point where only routing is missing.

Run with KiCad's python (it imports pcbnew), after tools/make_r5_sch.py:

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/make_r5_pcb.py
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/route_r5.py
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/brand_r1.py

What changes against r4:
  - IC2 + IC5 (two DIP-24 GALs) make room for IC2, an ATF1502AS in a PLCC-44 socket;
  - IC4 (NE555), C19, C20 and R9 go: the reset generator is inside the CPLD now;
  - the space that frees is used to spread the lower half out (PLACE below): the CPLD moves up
    under the memories it selects, the bank register lies below it, the pull-ups sit in a row
    where C20 was, and the bottom edge carries LED1, LED2, S1 (RESET) and J8 (JTAG) evenly spaced;
  - every pad takes its net from the r5 schematic's netlist, so board and schematic agree;
  - all signal copper goes (tools/route_r5.py routes every signal afresh); the r4 power copper,
    planes and the upper half of the placement stay;
  - design/solderdemon_6502.csv, the component list, is rewritten from the board.

The SolderDemon identity (logo, names, title block, revision r1) is added last, on the routed
board, by tools/brand_r1.py.
"""
from pathlib import Path
import os, re, subprocess, tempfile, uuid
import xml.etree.ElementTree as ET
import pcbnew as pcb

ROOT = Path(__file__).resolve().parents[1]
KICAD = ROOT / 'design'
NAME = 'solderdemon_6502'                                # SolderDemon 6502 r1; r4 was rosco_6502
BOARD = KICAD / f'{NAME}.kicad_pcb'
PROJECT = [KICAD / f'{NAME}.kicad_pro', KICAD / f'{NAME}.kicad_prl']
BASE = 'febedf81d62ee84a51998f37c9de908616646e20'                                          # r4, as last committed
CLI = os.environ.get('KICAD_CLI', 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')

REMOVE = {'IC2', 'IC4', 'IC5', 'C19', 'C20', 'R9'}
POWER = {'VCC', 'GND'}                                    # carried by the In1/In2 planes

# new or moved parts: courtyard centre (mm, board coordinates) and rotation (degrees)
PLACE = {
    'IC2': ((148.5, 113.0), 90),       # CPLD, right under U2/U3; its outputs face up and left
    'C12': ((132.3, 108.5), 90),       # IC2 decoupling, left
    'C8':  ((162.7, 113.0), 90),       # IC2 decoupling, right
    'R7':  ((167.2, 98.6), 0),         # /RESET pull-up, in a row where C20 and R9 were; clear of
                                       # the In1 no-fill area by J5, so the VCC pads reach the plane
    'R8':  ((167.2, 102.4), 0),        # S1 pull-up
    'R11': ((167.2, 106.2), 0),        # /DUADTACK pull-up
    'R12': ((127.8, 130.0), 0),        # DUART /IACK pull-up and the LED resistors: 4.4 mm apart
    'R5':  ((127.8, 134.4), 0),        #   instead of r4's 3.8, now that the column has room
    'R6':  ((127.8, 138.8), 0),
    'J3':  ((117.0, 126.0), 180),      # SPI / SD card header: turned round, pin 1 (CS) at the bottom
    'U4':  ((148.0, 133.2), 90),       # bank register, lying under the CPLD
    'C10': ((162.5, 133.2), 90),       # U4 decoupling
    'S1':  ((143.5, 145.0), 0),        # bottom edge: LED1, LED2, RESET, JTAG
    'J8':  ((157.5, 145.0), -90),
}
LIB = 'C:/Program Files/KiCad/10.0/share/kicad/footprints/'

# silkscreen: r4 texts that no longer describe anything, the ones that follow a part, the new ones
DROP_TEXT = {'ADDRESS DECODER', 'GLUE LOGIC'}
TEXT_ON = {'RESET': ('S1', -4.7), 'BANK REGISTER': ('U4', 0.0)}      # text -> (part, dy from its centre)
NEW_TEXT = [('CPLD', 'IC2', 0.0), ('JTAG', 'J8', -4.7)]
COPPER_TEXT = {'r4': 'r5'}
# J3's pin labels are loose board texts in a column at x = 114.77; turning J3 round mirrors them
J3_LABELS = {'CS', 'CK', 'COPI', 'CIPO', 'VCC', 'GND'}
J3_LABEL_X, J3_LABEL_SPAN = 114.77, 119.66 + 132.36     # first + last label y: mirror is span - y
SMALL_TEXT = {'BANK REGISTER': 1.0}               # mm; fits between U4's pin rows
REF_AT = {'R7': (0, 0), 'R8': (0, 0), 'R11': (0, 0), 'C8': (3.0, 0), 'C13': (0, -2.8), 'C14': (0, -2.8), 'J3': (0, -8.7)}   # reference text, from the part's centre


def mm(v): return pcb.ToMM(v)
def MM(x, y): return pcb.VECTOR2I(pcb.FromMM(x), pcb.FromMM(y))


def board_net(name):
    """KiCad escapes '/' in board net names."""
    return name.replace('/', '{slash}')


def r5_netlist():
    """ref -> {pin: net}, and ref -> value, from KiCad's own netlist of the r5 schematic."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / 'net.xml'
        subprocess.run([CLI, 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(out),
                        str(KICAD / f'{NAME}.kicad_sch')], check=True, capture_output=True)
        root = ET.parse(out).getroot()
    pins, comps = {}, {}
    for c in root.iter('comp'):
        comps[c.get('ref')] = (c.findtext('value'), c.findtext('footprint'))
    for net in root.iter('net'):
        for n in net.iter('node'):
            pins.setdefault(n.get('ref'), {})[n.get('pin')] = net.get('name')
    return pins, comps


def courtyard_box(fp, grow=0.0):
    """Courtyard bounds; the body without its texts for footprints that have none (S1's B3F-10XX)."""
    crt = fp.GetCourtyard(pcb.F_CrtYd)
    bb = crt.BBox() if crt.OutlineCount() else fp.GetBoundingBox(False)
    bb.Inflate(pcb.FromMM(grow))
    return bb


def place(fp, centre, rot):
    """Rotate `fp`, then move it so that its courtyard is centred on `centre`."""
    fp.SetOrientationDegrees(rot)
    fp.Move(MM(centre[0], centre[1]) - courtyard_box(fp).GetCenter())


# ---- erosion ------------------------------------------------------------------------------

def erode(b, nets):
    """Remove tracks and vias of `nets` that have a free end, until none is left. Returns count.

    The geometry is read out of pcbnew once and the fixpoint is found in plain Python: thousands
    of small swig calls in a loop (HitTest, VECTOR2I arithmetic) corrupt KiCad 10's swig type
    table, after which every call returns a bare SwigPyObject.
    """
    TOL = 1000                                               # 1 um, in nm
    pads = {}                                                # net -> [(layers, x1, y1, x2, y2)]
    for fp in b.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            layers = {l for l in (pcb.F_Cu, pcb.In1_Cu, pcb.In2_Cu, pcb.B_Cu) if p.IsOnLayer(l)}
            pads.setdefault(p.GetNetname(), []).append((layers, bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
    segs, vias = {}, {}                                      # index -> geometry, and index -> pcbnew item
    items = [t for t in b.GetTracks() if t.GetNetname() in nets]
    for i, t in enumerate(items):
        if isinstance(t, pcb.PCB_VIA):
            p = t.GetPosition()
            vias[i] = (t.GetNetname(), p.x, p.y, t.GetWidth(pcb.F_Cu) // 2)
        else:
            s, e = t.GetStart(), t.GetEnd()
            segs[i] = (t.GetNetname(), t.GetLayer(), s.x, s.y, e.x, e.y)

    def on_pad(net, layer, x, y):
        return any((layer is None or layer in ls) and x1 <= x <= x2 and y1 <= y <= y2
                   for ls, x1, y1, x2, y2 in pads.get(net, []))

    def on_seg(x, y, sx, sy, ex, ey):
        dx, dy = ex - sx, ey - sy
        L2 = dx * dx + dy * dy
        u = 0 if L2 == 0 else max(0.0, min(1.0, ((x - sx) * dx + (y - sy) * dy) / L2))
        return (sx + u * dx - x) ** 2 + (sy + u * dy - y) ** 2 <= TOL * TOL

    def anchored(me, net, layer, x, y):
        if on_pad(net, layer, x, y): return True
        if any(n == net and (vx - x) ** 2 + (vy - y) ** 2 <= r * r for n, vx, vy, r in vias.values()): return True
        return any(j != me and n == net and l == layer and on_seg(x, y, sx, sy, ex, ey)
                   for j, (n, l, sx, sy, ex, ey) in segs.items())

    doomed = set()
    while True:
        new = set()
        for i, (n, l, sx, sy, ex, ey) in segs.items():
            if not (anchored(i, n, l, sx, sy) and anchored(i, n, l, ex, ey)):
                new.add(i)
        for i, (n, vx, vy, r) in vias.items():
            if n in POWER: continue                          # a power via always lands on its plane
            # KiCad calls a via dangling unless copper reaches it on two layers
            layers = {l for m, l, sx, sy, ex, ey in segs.values()
                      if m == n and ((sx - vx) ** 2 + (sy - vy) ** 2 <= r * r or (ex - vx) ** 2 + (ey - vy) ** 2 <= r * r)}
            if len(layers) < 2 and not on_pad(n, None, vx, vy):
                new.add(i)
        if not new:
            break
        for i in new:
            segs.pop(i, None); vias.pop(i, None)
        doomed |= new
    for i in doomed:
        b.Delete(items[i])
    return len(doomed)


def write_bom(b, path):
    """The component CSV in the format of r4's design/kicad/rosco_6502.csv: one row per footprint + value."""
    groups = {}
    for fp in sorted(b.GetFootprints(), key=lambda f: (f.GetValue(), f.GetReference())):
        if len(fp.Pads()) == 0: continue                     # logos
        key = (str(fp.GetFPID().GetUniStringLibItemName()), fp.GetValue())
        groups.setdefault(key, []).append(fp.GetReference())
    lines = ['"Id";"Designator";"Footprint";"Quantity";"Designation";"Supplier and ref";']
    for i, ((foot, value), refs) in enumerate(sorted(groups.items(), key=lambda kv: kv[0][1]), 1):
        refs.sort(key=lambda r: (re.sub(r'\d', '', r), int(re.sub(r'\D', '', r) or 0)))
        lines.append(f'{i};"{",".join(refs)}";"{foot}";{len(refs)};"{value}";;;')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')


def main():
    BOARD.write_bytes(subprocess.run(['git', 'show', f'{BASE}:design/kicad/rosco_6502.kicad_pcb'], cwd=ROOT,
                                     check=True, capture_output=True).stdout)
    # pcbnew rewrites the project file on save; it holds the DRC rules and is never generated
    kept = {f: f.read_bytes() for f in PROJECT if f.exists()}
    b = pcb.LoadBoard(str(BOARD))
    pins, comps = r5_netlist()

    # ---- remove the r4 parts, and every signal track: route_r5.py routes them all afresh ----
    # Collect first, delete after: in KiCad 10's swig, once an item has been Remove()d the next
    # Pads() call comes back as a bare SwigPyObject. Delete() of items gathered up front is safe.
    gone = [b.FindFootprintByReference(ref) for ref in sorted(REMOVE)]
    gone += [t for t in b.GetTracks() if t.GetNetname() not in POWER]
    for item in gone:
        b.Delete(item)
    del gone

    # ---- new parts ----
    ic3 = b.FindFootprintByReference('IC3')
    ic2 = pcb.FOOTPRINT(ic3)                                 # same PLCC-44 socket footprint
    ic2.SetReference('IC2'); ic2.SetValue('ATF1502AS-10JU44')
    b.Add(ic2)

    j8 = pcb.FootprintLoad(LIB + 'Connector_PinHeader_2.54mm.pretty', 'PinHeader_2x05_P2.54mm_Vertical')
    j8.SetReference('J8'); j8.SetValue('JTAG')
    b.Add(j8)

    for ref, (centre, rot) in PLACE.items():
        place(b.FindFootprintByReference(ref), centre, rot)

    # deterministic identities, and the link to the schematic symbol
    sheet = uuid.UUID(_sheet_uuid())
    for fp, ref in ((ic2, 'IC2'), (j8, 'J8')):
        sym = uuid.uuid5(sheet, f'symbol {ref}')
        fp.SetPath(pcb.KIID_PATH(f'/{sym}'))
        fp.SetFPIDAsString(comps[ref][1])

    # ---- nets for every pad, from the r5 netlist ----
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref not in pins: continue
        value = comps[ref][0]
        if fp.GetValue() != value: fp.SetValue(value)
        for p in fp.Pads():
            name = pins[ref].get(p.GetNumber())
            if name is None:
                p.SetNetCode(0); continue
            name = board_net(name)
            net = b.FindNet(name)
            if net is None:
                net = pcb.NETINFO_ITEM(b, name); b.Add(net)
            p.SetNet(net)

    # ---- silkscreen and copper text ----
    texts = [d for d in b.GetDrawings() if isinstance(d, pcb.PCB_TEXT)]
    for d in texts:
        t = d.GetText()
        if t in TEXT_ON: d.SetPosition(anchor(b, *TEXT_ON[t]))
        pos = d.GetPosition()
        if t in J3_LABELS and abs(pcb.ToMM(pos.x) - J3_LABEL_X) < 0.05:
            d.SetPosition(MM(J3_LABEL_X, J3_LABEL_SPAN - pcb.ToMM(pos.y)))
        if t in SMALL_TEXT:
            d.SetTextSize(pcb.VECTOR2I(pcb.FromMM(SMALL_TEXT[t]), pcb.FromMM(SMALL_TEXT[t])))
            d.SetTextThickness(pcb.FromMM(SMALL_TEXT[t] * 0.15))
            d.SetTextAngleDegrees(0)                         # r4 ran it upright beside U4
        elif t in COPPER_TEXT: d.SetText(COPPER_TEXT[t])
    for d in [d for d in texts if d.GetText() in DROP_TEXT]:
        b.Delete(d)
    ref_text = next(d for d in b.GetDrawings() if isinstance(d, pcb.PCB_TEXT) and d.GetText() == 'RESET')
    for s, ref, dy in NEW_TEXT:
        t = pcb.PCB_TEXT(b)
        t.SetText(s); t.SetLayer(pcb.F_SilkS); t.SetPosition(anchor(b, ref, dy))
        t.SetTextSize(ref_text.GetTextSize()); t.SetTextThickness(ref_text.GetTextThickness())
        b.Add(t)

    reroute_ic3_vcc_bridge(b)
    bridge_socket_planes(b)

    for ref, (dx, dy) in REF_AT.items():
        c = courtyard_box(b.FindFootprintByReference(ref)).GetCenter()
        b.FindFootprintByReference(ref).Reference().SetPosition(pcb.VECTOR2I(c.x + pcb.FromMM(dx), c.y + pcb.FromMM(dy)))

    tb = b.GetTitleBlock()
    tb.SetRevision('5'); tb.SetDate('2026-09-26')

    pcb.ZONE_FILLER(b).Fill(b.Zones())
    pcb.SaveBoard(str(BOARD), b)
    for f, data in kept.items():
        f.write_bytes(data)
    write_bom(b, KICAD / f'{NAME}.csv')
    b.BuildConnectivity()
    print('tracks+vias:', len(b.GetTracks()), ' unrouted connections:',
          b.GetConnectivity().GetUnconnectedCount(True))


def bridge_socket_planes(b, ref='IC2', out=3.0, width=0.4):
    """Tie IC2's power pads to the planes.

    The socket's two pin rows sit on a 2.54 mm grid, too tight for the plane to flow between them,
    so the plane inside the ring is an island, and a power pad in the inner row lands on that
    island only. r4 had the same problem with IC3 and hand-drew plane-layer tracks out of the
    ring; this does the same, before routing, so the router treats them as fixed power copper. From an inner-row power pad the track runs at 45 degrees to the
    middle of the gap between two outer-row pins, then straight out. Power pads also get solid
    (not thermal) plane connections.
    """
    layer = {'VCC': pcb.In1_Cu, 'GND': pcb.In2_Cu}
    fp = b.FindFootprintByReference(ref)
    pads = [(p.GetNumber(), p.GetNetname(), p.GetNet(), p.GetPosition()) for p in fp.Pads()]
    for p in fp.Pads():
        if p.GetNetname() in layer:
            p.SetLocalZoneConnection(pcb.ZONE_CONNECTION_FULL)
    xs = [q.x for *_, q in pads]; ys = [q.y for *_, q in pads]
    cx, cy = (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2
    half = max(max(xs) - cx, max(ys) - cy)                  # the outer row's distance from the centre
    g = pcb.FromMM(1.27)
    for num, net, netinfo, q in pads:
        if net not in layer: continue
        dx, dy = q.x - cx, q.y - cy
        if max(abs(dx), abs(dy)) > half - pcb.FromMM(0.5): continue      # outer row: the plane reaches it
        if abs(dx) > abs(dy): n, t = ((1 if dx > 0 else -1), 0), (0, 1 if dy <= 0 else -1)
        else: n, t = (0, (1 if dy > 0 else -1)), (1 if dx <= 0 else -1, 0)
        a = pcb.VECTOR2I(q.x + (n[0] + t[0]) * g, q.y + (n[1] + t[1]) * g)
        e = pcb.VECTOR2I(a.x + n[0] * pcb.FromMM(out), a.y + n[1] * pcb.FromMM(out))
        for s_, e_ in ((q, a), (a, e)):
            tr = pcb.PCB_TRACK(b)
            tr.SetStart(s_); tr.SetEnd(e_); tr.SetWidth(pcb.FromMM(width))
            tr.SetLayer(layer[net]); tr.SetNet(netinfo)
            b.Add(tr)
        print(f'plane bridge: {ref} pad {num} ({net})')


def reroute_ic3_vcc_bridge(b):
    """r4 tied IC3's inner VCC plane island to the outside with an In1 track that ended on J3's
    VCC pin. With J3 turned round that pin is CK, so the track now stops in the open plane at
    x = 112.5 mm, in the same corridor between IC3's pins, and joins the plane there."""
    y = pcb.FromMM(130.5493)
    for t in [t for t in b.GetTracks() if t.GetNetname() == 'VCC' and t.GetLayer() == pcb.In1_Cu]:
        s, e = t.GetStart(), t.GetEnd()
        if abs(s.y - y) < 1000 and abs(e.y - y) < 1000 and max(s.x, e.x) > pcb.FromMM(116):
            t.SetEnd(MM(112.5, 130.5493)) if e.x > s.x else t.SetStart(MM(112.5, 130.5493))
    for t in [t for t in b.GetTracks() if t.GetNetname() == 'VCC' and t.GetLayer() == pcb.In1_Cu
              and min(t.GetStart().x, t.GetEnd().x) > pcb.FromMM(116)]:
        b.Delete(t)


def anchor(b, ref, dy):
    """A point `dy` mm below the centre of `ref`'s courtyard."""
    c = courtyard_box(b.FindFootprintByReference(ref)).GetCenter()
    return pcb.VECTOR2I(c.x, c.y + pcb.FromMM(dy))


def _sheet_uuid():
    text = (KICAD / f'{NAME}.kicad_sch').read_text(encoding='utf-8')
    return re.search(r'\(uuid ([0-9a-f-]{36})\)', text).group(1)


if __name__ == '__main__':
    main()
