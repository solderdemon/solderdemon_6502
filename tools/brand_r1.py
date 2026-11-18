"""SolderDemon identity for the SolderDemon 6502 r1 board.

Run after make_r1_pcb.py and before route_r5.py, so the router verifies the final silkscreen. As on the SolderDemon busboard and solderdemon_m68k:
  1. the rosco_6502 logotype at the top edge, the open hardware logo in the top right corner and
     the RoHS logo on the back go; the upper front area stays free for the components;
  2. the SolderDemon pixel-art logo (tools/make_logo.py) goes on the front between the two PLCC
     sockets, and on the back between the 65C02's pad columns; its name and revision run under it;
  3. the copper revision mark in the top left corner becomes r1; the copyright line on the back
     reads "(c)2026 SolderDemon". The title block names SolderDemon and keeps one line on the
     rosco_6502 origin: CERN OHL 3.1 asks for the notice in the design files (not on the board).

Only silkscreen changes, and one copper text of the same size in the same place, so the routing
stays valid. Safe to run again.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/make_logo.py 11.5
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/brand_r1.py
"""
from pathlib import Path
import sys

import pcbnew as pcb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_r5_pcb import BOARD, KICAD, PROJECT, courtyard_box  # noqa: E402

LOGO = ('solderdemon_6502', 'SolderDemon_Logo')
BACK_LOGO = (0.0, -16.0)                                     # from the centre of IC1, between its pad columns
OLD_LOGOS = {'rosco_6502:rosco_6502', 'Symbol:OSHW-Logo2_7.3x6mm_SilkScreen', 'Symbol:RoHS-Logo_6mm_SilkScreen'}
COPYRIGHT = {'(c)2022-2023 Ross Bamford & Contributors': '(c)2026 SolderDemon'}   # back silkscreen
BACK_TEXT = [                                                # text, offset from IC1's centre, size, thickness
    ('SolderDemon', (2.0, 6.0), 1.6, 0.3),
    ('solderdemon_6502 r1', (-2.5, 6.0), 1.0, 0.2),
]
REVISION = {'r5': 'r1', 'r2': 'r1'}
TITLE = {
    'title': 'SolderDemon 6502', 'rev': 'r1', 'date': '2026-10-01', 'company': 'SolderDemon',
    'comments': ['Copyright (c)2026 SolderDemon', 'Open Source Hardware (CERN OHL v1.2)',
                 'Modified 2026-09-30 from rosco_6502 r4, (c)2022-2023 Ross Bamford & Contributors'],
}

mm = pcb.FromMM


def text(b, s, xy, size, thick, layer, angle=0):
    t = pcb.PCB_TEXT(b)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetMirrored(layer == pcb.B_SilkS)
    t.SetTextAngleDegrees(angle)
    t.SetTextSize(pcb.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(thick))
    t.SetHorizJustify(pcb.GR_TEXT_H_ALIGN_CENTER)
    t.SetVertJustify(pcb.GR_TEXT_V_ALIGN_CENTER)
    t.SetPosition(pcb.VECTOR2I(mm(xy[0]), mm(xy[1])))
    b.Add(t)


def main():
    kept = {f: f.read_bytes() for f in PROJECT if f.exists()}   # SaveBoard rewrites them
    b = pcb.LoadBoard(str(BOARD))
    lib, name = LOGO
    cpu, duart = (courtyard_box(b.FindFootprintByReference(r)) for r in ('IC1', 'IC3'))
    cx, cy = pcb.ToMM(cpu.GetCenter().x), pcb.ToMM(cpu.GetCenter().y)
    x, y = cx + BACK_LOGO[0], cy + BACK_LOGO[1]
    cpld = courtyard_box(b.FindFootprintByReference('IC2'))
    front_logo = ((pcb.ToMM(cpld.GetRight()) + pcb.ToMM(duart.GetLeft())) / 2 + 1.0, pcb.ToMM(duart.GetTop()) + 8.7)   # between the two sockets
    ours = {'SolderDemon 6502', 'solderdemon_6502 r2', 'OP5', 'OP3'} | {t[0] for t in BACK_TEXT}

    # collect first, delete after (KiCad 10's swig loses types once removed items are freed)
    gone = [fp for fp in b.GetFootprints() if fp.GetFPIDAsString() in OLD_LOGOS | {f'{lib}:{name}'}]
    gone += [d for d in b.GetDrawings() if isinstance(d, pcb.PCB_TEXT) and d.GetText() in ours]
    for item in gone:
        b.Delete(item)
    del gone

    for d in b.GetDrawings():
        if isinstance(d, pcb.PCB_TEXT) and d.GetText() in REVISION.keys() | COPYRIGHT.keys() | {'(c)2026 SolderDemon'}:
            d.SetText({**REVISION, **COPYRIGHT}.get(d.GetText(), d.GetText()))
            if d.GetText() == '(c)2026 SolderDemon':
                u1 = courtyard_box(b.FindFootprintByReference('U1')).GetCenter()   # between U1's pad columns
                d.SetPosition(u1)
                d.SetTextAngleDegrees(90)

    fp = pcb.FootprintLoad(str(KICAD / f'{lib}.pretty'), name)
    fp.SetFPID(pcb.LIB_ID(lib, name))
    fp.SetReference('LOGO1')
    b.Add(fp)
    fp.SetPosition(pcb.VECTOR2I(mm(x), mm(y)))
    fp.Flip(fp.GetPosition(), pcb.FLIP_DIRECTION_LEFT_RIGHT)

    front = pcb.FootprintLoad(str(KICAD / f'{lib}.pretty'), name)
    front.SetFPID(pcb.LIB_ID(lib, name))
    front.SetReference('LOGO2')
    b.Add(front)
    front.SetPosition(pcb.VECTOR2I(mm(front_logo[0]), mm(front_logo[1])))

    for s, (dx, dy), size, thick in BACK_TEXT:
        text(b, s, (cx + dx, cy + dy), size, thick, pcb.B_SilkS, 90)

    # The front legend names the physical parts only.
    for ref in ('LED1', 'LED2'):
        c = courtyard_box(b.FindFootprintByReference(ref)).GetCenter()
        xy = (pcb.ToMM(c.x), pcb.ToMM(c.y) - 5.0)
        field = b.FindFootprintByReference(ref).Reference()
        field.SetLayer(pcb.F_SilkS)
        field.SetMirrored(False)
        field.SetTextSize(pcb.VECTOR2I(mm(1.1), mm(1.1)))
        field.SetTextThickness(mm(0.165))
        field.SetPosition(pcb.VECTOR2I(mm(xy[0]), mm(xy[1])))

    # Put each reference inside the resistor body outline. The long axis of
    # these footprints is vertical, so rotate the text to fit all R1–R13.
    for fp in b.GetFootprints():
        if not fp.GetReference().startswith('R') or not fp.GetReference()[1:].isdigit():
            continue
        field = fp.Reference()
        field.SetLayer(pcb.F_SilkS)
        field.SetMirrored(False)
        field.SetTextAngleDegrees(90)
        field.SetTextSize(pcb.VECTOR2I(mm(0.8), mm(0.8)))
        field.SetTextThickness(mm(0.12))
        body = courtyard_box(fp).GetCenter()
        field.SetPosition(body)

    tb = b.GetTitleBlock()
    tb.SetTitle(TITLE['title']); tb.SetRevision(TITLE['rev']); tb.SetDate(TITLE['date'])
    tb.SetCompany(TITLE['company'])
    for i in range(9):
        tb.SetComment(i, TITLE['comments'][i] if i < len(TITLE['comments']) else '')

    pcb.ZONE_FILLER(b).Fill(b.Zones())
    pcb.SaveBoard(str(BOARD), b)
    for f, data in kept.items():
        f.write_bytes(data)
    b.BuildConnectivity()
    print('SolderDemon 6502 r1; unconnected:', b.GetConnectivity().GetUnconnectedCount(True))


if __name__ == '__main__':
    main()
