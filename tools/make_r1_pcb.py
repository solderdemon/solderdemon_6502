"""SolderDemon 6502 r1: bus header beside the CPU, I/O on the opposite edge.

Run with KiCad's python, then route and brand:

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/make_r1_pcb.py
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/make_logo.py 11.5
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/brand_r1.py
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/route_r5.py

Derived from r1 as committed (BASE), schematic and board. What changes:
  - the outline stays 100 x 100 mm; J5 keeps the position and pin order of the busboard: its pads
    are those of a right-angle 2x18 socket (pin 2 inboard of pin 1), so the host stands upright in
    the busboard's HOST slot;
  - the four DIPs stand side by side under the top edge, pin 1 up, on the 2.54 mm grid of J5's
    pins: CPU, bank RAM, low RAM, ROM, each with its decoupler over it;
  - under them: the CPU's oscillator, the bank register and the DUART's crystal; then the two
    PLCC sockets on one line (CPLD under the CPU, DUART by the headers) with the logo and JTAG
    between them; then a bottom row of indicators, RESET, all twelve resistors and bulk capacitors;
  - UART B, UART A, SD/SPI and power run down the right edge, each UART's supply jumper under it;
  - every track goes (route_r5.py routes the signals afresh); the In1 no-fill area r4 kept by
    J5 goes too, the plane bridges out of both PLCC sockets are redrawn.
"""
from pathlib import Path
import re, subprocess, sys
import pcbnew as pcb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_r5_pcb import (BOARD, KICAD, NAME, PROJECT, MM, courtyard_box, place,  # noqa: E402
                         bridge_socket_planes, write_bom)
from rename_lib import main as rename_lib                          # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'tools' / 'capacitors'))
from replace import replace_100nf
BASE = '9a91aaa1146b6eed95326ec53de45344636aaf9f'                                          # SolderDemon 6502 r1, as committed
SCH = KICAD / f'{NAME}.kicad_sch'
STOCK_J5 = 'Connector_PinHeader_2.54mm:PinHeader_2x18_P2.54mm_Vertical'
J5_FP = ('solderdemon_6502', 'PinSocket_2x18_P2.54mm_Horizontal_EdgeMount')   # see edge_socket()
J5_STOCK = ('Connector_PinSocket_2.54mm', 'PinSocket_2x18_P2.54mm_Horizontal')
LIB = 'C:/Program Files/KiCad/10.0/share/kicad/footprints/'
EDGE_L, EDGE_R = 84.0, 184.0                              # 100 x 100 mm outline
EDGE_T, EDGE_B = 49.0, 149.0
PLANE_EDGE_INSET = 0.6                                    # 0.5 mm copper-to-edge rule + margin
J5_PIN1 = (89.775, 63.425)                                # fixed for busboard compatibility

def gx(i): return J5_PIN1[0] + 2.54 * i                   # the 2.54 mm grid J5's pins stand on:
def gy(j): return J5_PIN1[1] + 2.54 * j                   # every DIP pad is on one of its nodes


# The four DIPs stand side by side under the top edge, pin 1 up, 20.32 mm apart. A DIP courtyard
# ends 1.6 mm outside its pad columns and 1.64 mm past its last pads; a PLCC-44 socket has a
# 24.59 mm square one.
CPU_X, U1_X, U2_X, U3_X = gx(5), gx(13), gx(21), gx(29)   # centre lines
DIP_TOP = gy(-3) - 1.64                                   # pin 1 of all four is on gy(-3)
CPU_BOT, U1_BOT, MEM_BOT = gy(16) + 1.64, gy(12) + 1.64, gy(10) + 1.64
LEFT, RIGHT = CPU_X - 9.22, U3_X + 9.22                   # the block of chips, 79.4 mm wide
CAP_Y = DIP_TOP - 2.145                                   # decouplers over the DIPs
PLCC = 24.59 / 2
PLCC_Y = CPU_BOT + 2.4 + PLCC                             # both sockets are on this line
CPLD_X = LEFT + PLCC
DUART_X = 154.0                                           # clear of the power jack
MID_Y = MEM_BOT + 1.8 + 5.395                             # bank register and crystal, under RAM and ROM
ROW_Y = 141.0                                             # bottom row: indicators, RESET, resistors, bulk capacitors
RES_X, RES_PITCH = 121.545, 3.2
EDGE_X = 181.25                                           # the header column on the right edge
LABEL_X = 177.9
REVISION_AT = (88.505, 126.0)                               # copper revision mark, under C16

# loose texts that follow a part (the texts' r1 positions are near its r1 centre)
TEXT_WITH = {
    '65C02': 'IC1', 'SolderDemon': 'IC1', 'solderdemon_6502 r1': 'IC1',
    '5VDC Only!': 'J7',
}

# the row of resistors, left to right: RDY, LED1, LED2, S1, BE, NMI, X1 EN, /DUADTACK, /RESET, IRQ,
# /IACK, ROM pin 27. The order and the way up are the ones with the shortest connections.
BANK = ['R1', 'R5', 'R6', 'R8', 'R2', 'R4', 'R10', 'R11', 'R7', 'R3', 'R12', 'R13']
BANK_ROT = {'R13': -90}

# courtyard centre (mm) and rotation (degrees) of every part but J5 and the mounting holes
PLACE = {
    # the row of DIPs: CPU, bank RAM, low RAM, ROM, each with its decoupler over it
    'IC1': ((CPU_X, gy(6.5)), 0),
    'U1':  ((U1_X, gy(4.5)), 0),
    'U2':  ((U2_X, gy(3.5)), 0),
    'U3':  ((U3_X, gy(3.5)), 0),
    'C1':  ((CPU_X - 9.22 + 2.345, CAP_Y), 0),
    'C2':  ((CPU_X + 9.22 - 2.345, CAP_Y), 0),
    'C3':  ((U1_X - 9.22 + 3.345, CAP_Y), 0),
    'C15': ((U2_X - 9.22 + 2.345, CAP_Y), 0),
    'C4':  ((U3_X - 9.22 + 2.345, CAP_Y), 0),
    'JP3': ((U3_X + 9.22 - 1.695, CAP_Y), 0),
    # under the RAM: the CPU's oscillator
    'X1':  ((U1_X + 9.22 - 6.645, U1_BOT + 1.5 + 6.645), 0),
    'C11': ((U1_X - 9.22 + 1.545, U1_BOT + 3.5 + 2.345), 90),
    # under low RAM and ROM: the bank register and the DUART's crystal between its capacitors
    'C10': ((U2_X - 9.22 + 1.545, MID_Y), 90),
    'U4':  ((U2_X - 9.22 + 3.09 + 0.6 + 10.545, MID_Y), 90),
    'C14': ((RIGHT - 1.6, MID_Y), 90),
    'Q1':  ((RIGHT - 3.2 - 0.5 - 2.845, MID_Y), 90),
    'C13': ((RIGHT - 3.2 - 0.5 - 5.69 - 0.5 - 1.6, MID_Y), 90),
    # the two PLCC sockets on one line, JTAG between them
    'IC2': ((CPLD_X, PLCC_Y), 0),
    'IC3': ((DUART_X, PLCC_Y), 0),
    'C9':  ((DUART_X - PLCC + 2.345, PLCC_Y - PLCC - 2.145), 0),
    'C12': ((CPLD_X + PLCC + 0.6 + 1.545, PLCC_Y - 5.0), 90),
    'C8':  ((CPLD_X + PLCC + 0.6 + 1.545, PLCC_Y + 5.0), 90),
    'J8':  (((CPLD_X + DUART_X) / 2 + 1.0, PLCC_Y + PLCC - 3.6), -90),
    # bottom row: the two indicators and RESET under the CPLD, the resistors, the bulk capacitors
    'LED1': ((LEFT + 3.27, ROW_Y), 0),
    'LED2': ((LEFT + 6.54 + 1.0 + 3.27, ROW_Y), 0),
    'S1':   ((LEFT + 2 * PLCC - 4.775, ROW_Y), 0),
    'C18':  ((163.15, ROW_Y), 0),
    'C17':  ((171.25, ROW_Y), 0),
    # right edge, top to bottom: UART B, UART A, SD/SPI with each UART's supply jumper under it, power
    'J2':  ((EDGE_X, 67.235), 0),
    'JP2': ((EDGE_X - 1.25, 77.9), 90),
    'J1':  ((EDGE_X, 88.55), 0),
    'JP1': ((EDGE_X - 1.25, 99.2), 90),
    'J3':  ((EDGE_X, 109.85), 180),
    'J7':  ((175.0, 125.5), 180),
    'J6':  ((EDGE_X, 136.3), 0),
    # the bulk capacitor stands under the bus header it buffers
    'C16': ((88.505, 113.5), 0),
}
PLACE.update({r: ((RES_X + RES_PITCH * i, ROW_Y), BANK_ROT.get(r, 90)) for i, r in enumerate(BANK)})
TEXT_ON = {'CPLD': ('IC2', 0.0), 'DUART': ('IC3', 0.0), 'RESET': ('S1', -5.0),
           'BANK\nRAM': ('U1', -6.0), 'AS6C4008': ('U1', 6.0),
           'LOW\nRAM': ('U2', -6.0), 'AS6C62256': ('U2', 6.0),
           'ROM': ('U3', -6.0), 'AT28C64B\n~or~\nAT28C256': ('U3', 6.0)}
TEXT_ROT = {}
DROP_TEXT_AT = {('ROM', 96.31)}                            # r4's second ROM label, where the pull-ups are now
# header pin labels: r1 had them as loose texts; they are redrawn beside the new column
PIN_LABELS = {
    'J2': ['GND', 'CTS', 'VCC', 'TxD', 'RxD', 'RTS'],
    'J1': ['GND', 'CTS', 'VCC', 'TxD', 'RxD', 'RTS'],
    'J3': ['CS', 'CK', 'COPI', 'CIPO', 'VCC', 'GND'],
}
HEADER_TITLE = {'J2': 'J2 UART B', 'J1': 'J1 UART A', 'J3': 'J3 SD/SPI'}
OLD_LABELS = {'GND', 'CTS', 'VCC', 'TxD', 'RxD', 'RTS', 'CIPO', 'COPI', 'CK', 'CS', 'Non-standard ROM',
              'UART B', 'J1 - UART A', '5VDC', 'BANK REGISTER', '65C02', 'JTAG'}
REF_AT = {'IC2': (0, 2.6), 'IC3': (0, 2.6), 'U4': (0, 0),
          'C1': (4.1, 0), 'C2': (-4.1, 0), 'C3': (4.1, 0), 'C15': (4.1, 0), 'C4': (4.1, 0), 'JP3': (-3.4, 0),
          'C9': (4.2, 0), 'C10': (0, 3.3), 'C11': (0, 3.3), 'C8': (0, 3.2), 'C12': (0, -3.2),
          'C13': (0, 5.0), 'C14': (0, 5.0), 'Q1': (0, 6.9),
          'C16': (0, 4.6), 'C17': (0, 5.0), 'C18': (0, 4.4),
          'JP1': (-5.9, 0), 'JP2': (-5.9, 0),
          'J1': (0, 0), 'J2': (0, 0), 'J3': (0, 0), 'J6': (0, 0)}
DIP_REF = {'IC1': 0.0, 'U1': 3.5, 'U2': 3.5, 'U3': 1.0}       # reference beside the decoupler: dx from the centre line
SMALL_REF = ('C1', 'C2', 'C3', 'C4', 'C8', 'C9', 'C10', 'C11', 'C12', 'C13', 'C14', 'C15', 'Q1', 'JP1', 'JP2', 'JP3')
TEXT_SIZE = {'RESET': 1.2}
SOLID_VCC = {'IC1': {'8', '38'}, 'J8': {'4'}}


def git_show(path):
    return subprocess.run(['git', 'show', f'{BASE}:{path}'], cwd=ROOT, check=True, capture_output=True).stdout


def edge_socket():
    """The stock right-angle 2x18 socket with its silkscreen clipped at the board edge.

    Its pads are the stock 2x18 header mirrored about pin 1's column (pin 2 at x = -2.54), which is
    what J5 has carried since r1 for the busboard's pin order. The body overhangs the left edge by
    about 6.7 mm; silk lines out there would only draw DRC warnings, so they end 0.3 mm inside the
    edge. Fab, courtyard and the 3D model stay as stock: they describe the real part."""
    src = Path(LIB + f'{J5_STOCK[0]}.pretty/{J5_STOCK[1]}.kicad_mod').read_text(encoding='utf-8')
    clip = EDGE_L - J5_PIN1[0] + 0.3                        # x of the clip line, relative to pin 1
    num = r'(-?\d+(?:\.\d+)?)'

    def clipped(m):
        x1, y1, x2, y2 = map(float, m.group(1, 2, 3, 4))
        if '(layer "F.SilkS")' not in m.group(0):
            return m.group(0)
        if max(x1, x2) < clip:
            return ''
        x1, x2 = max(x1, clip), max(x2, clip)
        return m.group(0).replace(m.group(1), f'{x1:g}', 1).replace(f'(end {m.group(3)} ', f'(end {x2:g} ', 1)
    out = re.sub(rf'\n\t\(fp_line\n\t\t\(start {num} {num}\)\n\t\t\(end {num} {num}\).*?\n\t\)', clipped, src, flags=re.S)
    assert out.count('(fp_line') < src.count('(fp_line')
    out = out.replace(f'"{J5_STOCK[1]}"', f'"{J5_FP[1]}"', 1)
    out = out.replace('(descr "', '(descr "On the board edge, silkscreen clipped 0.3 mm inside it; ', 1)
    path = KICAD / f'{J5_FP[0]}.pretty' / f'{J5_FP[1]}.kicad_mod'
    path.write_text(out, encoding='utf-8', newline='\n')
    return path


def mark_j5(b):
    """'PIN 1' and a filled triangle over J5's pin 1: the socket hides the square pad, and the
    busboard header takes the socket either way round."""
    x, y = J5_PIN1
    stale = [d for d in b.GetDrawings() if d.GetLayer() == pcb.F_SilkS and
             (isinstance(d, pcb.PCB_TEXT) and d.GetText() == 'PIN 1' or
              isinstance(d, pcb.PCB_SHAPE) and d.GetShape() == pcb.SHAPE_T_POLY and
              (d.GetCenter() - MM(x, y)).EuclideanNorm() < pcb.FromMM(5))]
    for d in stale:                                          # re-runnable: replace earlier marks
        b.Remove(d)
    ref = b.FindFootprintByReference('J5').Reference()
    ref.SetPosition(MM(x - 3.28, y - 4.2))  # left of PIN 1, on the same text baseline
    label(b, 'PIN 1', (x, y - 4.2), 0.8)
    tri = pcb.PCB_SHAPE(b, pcb.SHAPE_T_POLY)
    tri.SetPolyPoints(pcb.VECTOR_VECTOR2I([MM(x, y - 1.7), MM(x - 0.7, y - 2.9), MM(x + 0.7, y - 2.9)]))
    tri.SetFilled(True); tri.SetWidth(0); tri.SetLayer(pcb.F_SilkS)
    b.Add(tri)
    return stale                                         # keep removed items referenced


def patch_schematic():
    """Use the right-angle bus socket and remove the standalone CS2 pin header."""
    text = git_show(f'design/kicad/{NAME}.kicad_sch').decode('utf-8')
    assert text.count(f'"Footprint" "{STOCK_J5}"') == 1
    text = text.replace(f'"Footprint" "{STOCK_J5}"', f'"Footprint" "{J5_FP[0]}:{J5_FP[1]}"')
    text = text.replace('Capacitor_THT:C_Rect_L4.0mm_W2.5mm_P2.50mm',
                        'SolderDemonCaps:C_Radial_5.08mm')
    text, n = re.subn(r'\n  \(symbol \(lib_id "Connector:Conn_01x01_Pin"\).*?\n  \)\n', '\n', text, flags=re.S)
    assert n == 1, f'expected one J4 symbol, found {n}'
    text, n = re.subn(r'\n  \(global_label "SPICS2" \(shape input\).*?\n  \)\n', '\n', text, flags=re.S)
    assert n == 1, f'expected one CS2 connector label, found {n}'
    SCH.write_bytes(text.encode('utf-8'))


def label(b, s, xy, size, rot=0, layer=pcb.F_SilkS):
    t = pcb.PCB_TEXT(b)
    t.SetText(s); t.SetLayer(layer)
    t.SetTextSize(pcb.VECTOR2I(pcb.FromMM(size), pcb.FromMM(size)))
    t.SetTextThickness(pcb.FromMM(size * 0.15))
    t.SetTextAngleDegrees(rot)
    t.SetPosition(MM(*xy))
    b.Add(t)


def centre(b, ref):
    return courtyard_box(b.FindFootprintByReference(ref)).GetCenter()


def resize_board(b):
    """Grow right and bottom edges while keeping J5 and the top-left datum fixed."""
    dx, dy = EDGE_R - 184.0, EDGE_B - 149.0
    for shape in b.GetDrawings():
        if not isinstance(shape, pcb.PCB_SHAPE) or shape.GetLayer() != pcb.Edge_Cuts:
            continue
        start, end = shape.GetStart(), shape.GetEnd()
        if shape.GetShape() == pcb.SHAPE_T_ARC:
            right = max(pcb.ToMM(start.x), pcb.ToMM(end.x)) > 180.0
            bottom = max(pcb.ToMM(start.y), pcb.ToMM(end.y)) > 145.0
            shape.Move(MM(dx if right else 0, dy if bottom else 0))
        else:
            def expand(point):
                x, y = pcb.ToMM(point.x), pcb.ToMM(point.y)
                return MM(x + (dx if x >= 180.0 else 0),
                          y + (dy if y >= 145.0 else 0))
            shape.SetStart(expand(start))
            shape.SetEnd(expand(end))
    for ref, mx, my in [('H2', dx, 0), ('H3', 0, dy), ('H4', dx, dy)]:
        b.FindFootprintByReference(ref).Move(MM(mx, my))
    for zone in b.Zones():
        outline = zone.Outline()
        if outline.OutlineCount() != 1 or outline.VertexCount() != 4:
            continue
        for i in range(4):
            p = outline.CVertex(i)
            x, y = pcb.ToMM(p.x), pcb.ToMM(p.y)
            outline.SetVertex(i, MM(x + (dx if x > 180 else 0),
                                    y + (dy if y > 145 else 0)))


def inset_plane_zones(b):
    """Keep the two internal planes clear of the routed board edge."""
    for zone in b.Zones():
        if zone.GetLayer() not in (pcb.In1_Cu, pcb.In2_Cu):
            continue
        outline = zone.Outline()
        if outline.OutlineCount() != 1 or outline.VertexCount() != 4:
            continue  # preserve the shaped inner-plane zone from the source board
        for i in range(4):
            vertex = outline.CVertex(i)
            x, y = pcb.ToMM(vertex.x), pcb.ToMM(vertex.y)
            outline.SetVertex(i, MM(EDGE_L + PLANE_EDGE_INSET if x < (EDGE_L + EDGE_R) / 2
                                    else EDGE_R - PLANE_EDGE_INSET,
                                    EDGE_T + PLANE_EDGE_INSET if y < (EDGE_T + EDGE_B) / 2
                                    else EDGE_B - PLANE_EDGE_INSET))


def fix_stackup(board_path):
    """Record a nominal 1.6 mm four-layer stackup in the exported Gerber job."""
    text = board_path.read_text(encoding='utf-8')
    for layer, material_type, thickness in ((1, 'prepreg', '0.21'),
                                            (2, 'core', '1.02'),
                                            (3, 'prepreg', '0.21')):
        pattern = rf'(\(layer "dielectric {layer}"\s+)\(type "[^"]+"\)\s+\(thickness [^)]+\)'
        replacement = rf'\g<1>(type "{material_type}")\n\t\t\t\t(thickness {thickness})'
        text, count = re.subn(pattern, replacement, text, count=1)
        assert count == 1, f'dielectric {layer} missing from stackup'
    board_path.write_text(text, encoding='utf-8')


def main():
    BOARD.write_bytes(git_show(f'design/kicad/{NAME}.kicad_pcb'))
    kept = {f: f.read_bytes() for f in PROJECT if f.exists()}
    edge_socket()
    patch_schematic()
    b = pcb.LoadBoard(str(BOARD))
    replaced_caps, kept_caps = replace_100nf(b)
    assert len(replaced_caps) == 10, replaced_caps
    resize_board(b)
    inset_plane_zones(b)
    b.GetDesignSettings().SetBoardThickness(pcb.FromMM(1.6))
    removed_j4 = b.FindFootprintByReference('J4')
    assert removed_j4 is not None
    b.Delete(removed_j4)

    # where the moving parts' texts are anchored, before anything moves
    anchors = {}
    for d in b.GetDrawings():
        if isinstance(d, pcb.PCB_TEXT) and d.GetText() in TEXT_WITH:
            c = centre(b, TEXT_WITH[d.GetText()])
            anchors[d.GetText(), d.GetPosition().x, d.GetPosition().y] = (TEXT_WITH[d.GetText()], d.GetPosition() - c)
    j7_centre = centre(b, 'J7')
    j7_silk = [d for d in b.GetDrawings() if isinstance(d, pcb.PCB_SHAPE) and d.GetLayer() == pcb.B_SilkS]
    jp3_power = [t for t in b.GetTracks() if t.GetNetname() == 'GND' and t.GetLayer() == pcb.F_Cu]

    # ---- all copper goes but JP3's SMD pad to plane link; the In1 no-fill area by the old J5 ----
    gone = [t for t in b.GetTracks() if t not in jp3_power]
    gone += [z for z in b.Zones() if z.GetIsRuleArea()]
    gone += [d for d in b.GetDrawings() if isinstance(d, pcb.PCB_TEXT) and (d.GetText() in OLD_LABELS or
             (d.GetText(), round(pcb.ToMM(d.GetPosition().y), 2)) in DROP_TEXT_AT)]
    for item in gone:
        b.Delete(item)
    del gone

    # ---- J5: the right-angle busboard socket, on the left edge ----
    old = b.FindFootprintByReference('J5')
    j5 = pcb.FootprintLoad(str(KICAD / f'{J5_FP[0]}.pretty'), J5_FP[1])
    j5.SetFPID(pcb.LIB_ID(*J5_FP))
    j5.SetReference('J5'); j5.SetValue(old.GetValue())
    j5.SetPath(old.GetPath())
    j5.SetPosition(MM(*J5_PIN1))
    b.Add(j5)
    nets = {p.GetNumber(): p.GetNet() for p in old.Pads()}
    for p in j5.Pads():
        p.SetNet(nets[p.GetNumber()])
    b.Delete(old)

    # ---- moves ----
    for ref, (c, rot) in PLACE.items():
        place(b.FindFootprintByReference(ref), c, rot)
    jp3_ground = next(p for p in b.FindFootprintByReference('JP3').Pads() if p.GetNetname() == 'GND')
    jp3_via = next(t for t in jp3_power if isinstance(t, pcb.PCB_VIA))
    jp3_trace = next(t for t in jp3_power if isinstance(t, pcb.PCB_TRACK))
    jp3_via.SetPosition(jp3_ground.GetPosition() + MM(0, -1.5))
    jp3_trace.SetStart(jp3_ground.GetPosition())
    jp3_trace.SetEnd(jp3_via.GetPosition())
    dj7 = centre(b, 'J7') - j7_centre
    for d in j7_silk:
        d.Move(dj7)
    b.FindFootprintByReference('REF**').Move(dj7)
    for d in b.GetDrawings():
        if isinstance(d, pcb.PCB_TEXT):
            key = (d.GetText(), d.GetPosition().x, d.GetPosition().y)
            if key in anchors:
                ref, off = anchors[key]
                d.SetPosition(centre(b, ref) + off)
            elif d.GetText() in TEXT_ON:
                ref, dy = TEXT_ON[d.GetText()]
                d.SetPosition(centre(b, ref) + MM(0, dy))
                d.SetTextAngleDegrees(TEXT_ROT.get(d.GetText(), 0))
                if d.GetText() in TEXT_SIZE:
                    size = TEXT_SIZE[d.GetText()]
                    d.SetTextSize(MM(size, size))
                    d.SetTextThickness(pcb.FromMM(size * 0.15))

    # ---- header labels, J6's polarity ----
    for ref, names in PIN_LABELS.items():
        fp = b.FindFootprintByReference(ref)
        for p in fp.Pads():
            label(b, names[int(p.GetNumber()) - 1], (LABEL_X, pcb.ToMM(p.GetPosition().y)), 0.8)
        if ref in HEADER_TITLE:
            label(b, HEADER_TITLE[ref], (LABEL_X - 2.6, pcb.ToMM(centre(b, ref).y)), 0.85, rot=90)
    j8 = courtyard_box(b.FindFootprintByReference('J8'))
    label(b, 'JTAG', (pcb.ToMM(j8.GetCenter().x), pcb.ToMM(j8.GetTop()) - 1.2), 1.0)
    mark_j5(b)
    for p in b.FindFootprintByReference('J6').Pads():
        name = {'VCC': '5V', 'GND': 'GND'}[p.GetNetname()]
        label(b, name, (LABEL_X, pcb.ToMM(p.GetPosition().y)), 0.8)

    for ref in ('IC2', 'IC3'):
        bridge_socket_planes(b, ref)
    # These supply pads sit between their neighbours' plane clearances and keep too few thermal
    # spokes. Solid pad connections preserve the VCC path without changing the signal layout.
    for ref, numbers in SOLID_VCC.items():
        for p in b.FindFootprintByReference(ref).Pads():
            if p.GetNumber() in numbers:
                p.SetLocalZoneConnection(pcb.ZONE_CONNECTION_FULL)

    for ref, (dx, dy) in REF_AT.items():
        c = centre(b, ref)
        b.FindFootprintByReference(ref).Reference().SetPosition(c + MM(dx, dy))
    for ref in SMALL_REF:
        field = b.FindFootprintByReference(ref).Reference()
        field.SetTextSize(MM(0.8, 0.8))
        field.SetTextThickness(pcb.FromMM(0.12))
        field.SetTextAngleDegrees(0)
        if ref in ('C13', 'C14'):
            field.SetHorizJustify(pcb.GR_TEXT_H_ALIGN_CENTER)
    for ref in BANK:
        fp = b.FindFootprintByReference(ref)
        field = fp.Reference()
        field.SetLayer(pcb.B_SilkS)
        field.SetMirrored(True)
        field.SetPosition(centre(b, ref))
        field.SetTextSize(MM(0.85, 0.85))
    for ref in BANK:
        b.FindFootprintByReference(ref).Reference().SetTextAngleDegrees(0)
    b.FindFootprintByReference('IC2').Reference().SetTextAngleDegrees(0)
    for ref in ('J1', 'J2', 'J3', 'J6'):               # named in the column's titles and labels
        b.FindFootprintByReference(ref).Reference().SetVisible(False)
    for ref, dx in DIP_REF.items():
        field = b.FindFootprintByReference(ref).Reference()
        field.SetPosition(MM(pcb.ToMM(centre(b, ref).x) + dx, CAP_Y))
        field.SetTextAngleDegrees(0)
    b.FindFootprintByReference('U4').Reference().SetTextAngleDegrees(0)

    for d in b.GetDrawings():                          # the copper revision mark: C1 stands where it was
        if isinstance(d, pcb.PCB_TEXT) and d.IsOnCopperLayer():
            d.SetPosition(MM(*REVISION_AT))

    tb = b.GetTitleBlock()
    tb.SetRevision('r1'); tb.SetDate('2026-10-01')

    pcb.ZONE_FILLER(b).Fill(b.Zones())
    pcb.SaveBoard(str(BOARD), b)
    fix_stackup(BOARD)
    for f, data in kept.items():
        f.write_bytes(data)
    write_bom(b, KICAD / f'{NAME}.csv')
    overlaps(b)
    rename_lib()                                       # the BASE files still name the library rosco_6502
    table = KICAD / 'fp-lib-table'
    source = table.read_text(encoding='utf-8')
    if '(name "SolderDemonCaps")' not in source:
        source = source.replace('\n)', '\n  (lib (name "SolderDemonCaps")(type "KiCad")(uri "${KIPRJMOD}/SolderDemonCaps.pretty")(options "")(descr "5.08 mm radial capacitor"))\n)')
        table.write_text(source, encoding='utf-8')


def overlaps(b):
    """Courtyard collisions and parts outside the outline, so a placement can be checked unrouted."""
    fps = [f for f in b.GetFootprints() if len(f.Pads())]
    boxes = {f.GetReference(): courtyard_box(f) for f in fps}
    refs = sorted(boxes)
    for i, a in enumerate(refs):
        A = boxes[a]
        if pcb.ToMM(A.GetLeft()) < EDGE_L or pcb.ToMM(A.GetRight()) > EDGE_R or \
           pcb.ToMM(A.GetTop()) < EDGE_T or pcb.ToMM(A.GetBottom()) > EDGE_B:
            print('outside:', a)
        for c in refs[i + 1:]:
            if A.Intersects(boxes[c]):
                print('overlap:', a, c)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--j5-mark-only':
        board = pcb.LoadBoard(str(BOARD))
        x, y = J5_PIN1
        board.FindFootprintByReference('J5').Reference().SetPosition(MM(x - 3.28, y - 4.2))
        pcb.SaveBoard(str(BOARD), board)
        print('aligned J5 with PIN 1')
    else:
        main()
