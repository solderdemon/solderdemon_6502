"""SolderDemon identity for the routed board: SolderDemon 6502 r1, the first SolderDemon revision.

Last step, after tools/route_r5.py. As on the SolderDemon busboard and solderdemon_m68k:
  1. the rosco_6502 logotype at the top edge, the open hardware logo in the top right corner and
     the RoHS logo on the back go; "SolderDemon 6502" takes the logotype's place, in plain KiCad type, between C16 and R13;
  2. the SolderDemon pixel-art logo (tools/make_logo.py) goes on the back, between the 65C02's rows
     of pins, the only place with 12 mm to spare; the name in large type and the board name run
     up the same column under it;
  3. the copper revision mark in the top left corner becomes r1; the copyright line on the back
     reads "(c)2026 SolderDemon". The title block names SolderDemon and keeps one line on the
     rosco_6502 origin: CERN OHL 3.1 asks for the notice in the design files (not on the board).

Only silkscreen changes, and one copper text of the same size in the same place, so the routing
stays valid. Safe to run again.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/make_logo.py 12.8
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/brand_r1.py
"""
from pathlib import Path
import sys

import pcbnew as pcb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_r5_pcb import BOARD, KICAD, PROJECT  # noqa: E402

LOGO = ('rosco_6502', 'SolderDemon_Logo', (99.23, 67.6))     # centred between IC1's pad rows
OLD_LOGOS = {'rosco_6502:rosco_6502', 'Symbol:OSHW-Logo2_7.3x6mm_SilkScreen', 'Symbol:RoHS-Logo_6mm_SilkScreen'}
COPYRIGHT = {'(c)2022-2023 Ross Bamford & Contributors': '(c)2026 SolderDemon'}   # back silkscreen
FRONT_NAME = ('SolderDemon 6502', (132.42, 51.75), 2.0, 0.35)
BACK_TEXT = [                                                # text, centre, size, thickness
    ('SolderDemon', (98.2, 90.5), 2.2, 0.4),
    ('solderdemon_6502 r1', (101.5, 90.5), 1.2, 0.2),
]
REVISION = {'r5': 'r1'}                                      # the copper text in the top left corner
TITLE = {
    'title': 'SolderDemon 6502', 'rev': 'r1', 'date': '2026-09-30', 'company': 'SolderDemon',
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
    lib, name, (x, y) = LOGO
    ours = {FRONT_NAME[0]} | {t[0] for t in BACK_TEXT}

    # collect first, delete after (KiCad 10's swig loses types once removed items are freed)
    gone = [fp for fp in b.GetFootprints() if fp.GetFPIDAsString() in OLD_LOGOS | {f'{lib}:{name}'}]
    gone += [d for d in b.GetDrawings() if isinstance(d, pcb.PCB_TEXT) and d.GetText() in ours]
    for item in gone:
        b.Delete(item)
    del gone

    for d in b.GetDrawings():
        if isinstance(d, pcb.PCB_TEXT) and d.GetText() in REVISION | COPYRIGHT:
            d.SetText({**REVISION, **COPYRIGHT}[d.GetText()])

    fp = pcb.FootprintLoad(str(KICAD / f'{lib}.pretty'), name)
    fp.SetFPID(pcb.LIB_ID(lib, name))
    fp.SetReference('LOGO1')
    b.Add(fp)
    fp.SetPosition(pcb.VECTOR2I(mm(x), mm(y)))
    fp.Flip(fp.GetPosition(), pcb.FLIP_DIRECTION_LEFT_RIGHT)

    s, xy, size, thick = FRONT_NAME
    text(b, s, xy, size, thick, pcb.F_SilkS)
    for s, xy, size, thick in BACK_TEXT:
        text(b, s, xy, size, thick, pcb.B_SilkS, angle=90)

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
