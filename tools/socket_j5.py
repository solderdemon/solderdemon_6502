"""J5 becomes the right-angle busboard socket.

The SolderDemon 6502 r1 J5 pads were the stock 2x18 header mirrored about pin 1's column, i.e.
exactly the pads of KiCad's `PinSocket_2x18_P2.54mm_Horizontal` (pin 2 at x = -2.54, body toward
the board edge). With a female right-angle socket there, the host stands upright in the busboard's
HOST slot, component side toward the busboard's left edge, and no ribbon cable is needed; a plain
36-way ribbon between the mirrored pads and the busboard's straight header would in fact swap every
odd/even pair (VCC onto A0). This script makes the board say so:

  - the J5 footprint on the board is replaced in place by the stock horizontal socket with its
    silkscreen clipped at the board edge (make_r1_pcb.edge_socket writes it into the project
    library), same pin 1 position, same nets; every pad must land where the old one was;
  - the schematic's J5 footprint field and the BOM follow;
  - the local mirrored-header footprint goes (make_r1_pcb.py no longer writes it);
  - 'PIN 1' and a triangle over pin 1 (make_r1_pcb.mark_j5), since the socket hides the square pad.
Re-runnable: each step checks whether it has been applied.

Run with KiCad's python:  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/socket_j5.py
"""
from pathlib import Path
import sys

import pcbnew as pcb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_r1_pcb

ROOT = Path(__file__).resolve().parent.parent
NAME = 'solderdemon_6502'
KICAD = ROOT / 'design'
BOARD = KICAD / f'{NAME}.kicad_pcb'
SCH = KICAD / f'{NAME}.kicad_sch'
BOM = KICAD / f'{NAME}.csv'
PROJECT = [KICAD / f'{NAME}.kicad_pro', KICAD / f'{NAME}.kicad_prl']
OLD = [(NAME, 'PinHeader_2x18_P2.54mm_Vertical_Mirrored'), make_r1_pcb.J5_STOCK]   # either may be on the board
NEW = make_r1_pcb.J5_FP


def copy_text(src, dst):
    dst.SetPosition(src.GetPosition())
    dst.SetTextSize(src.GetTextSize()); dst.SetTextThickness(src.GetTextThickness())
    dst.SetTextAngle(src.GetTextAngle()); dst.SetLayer(src.GetLayer())
    dst.SetVisible(src.IsVisible()); dst.SetMirrored(src.IsMirrored())


def swap_footprint(b):
    old = b.FindFootprintByReference('J5')
    was = tuple(old.GetFPIDAsString().split(':'))
    if was == NEW:
        print('J5 is already', ':'.join(NEW))
        return None, None
    assert was in OLD, was
    new = pcb.FootprintLoad(str(make_r1_pcb.edge_socket().parent), NEW[1])
    new.SetFPID(pcb.LIB_ID(*NEW))
    new.SetReference('J5'); new.SetValue(old.GetValue())
    new.SetField('Datasheet', old.GetFieldText('Datasheet'))
    new.SetPath(old.GetPath())
    new.SetSheetfile(old.GetSheetfile()); new.SetSheetname(old.GetSheetname())
    new.SetLayer(old.GetLayer())
    new.SetOrientation(old.GetOrientation())
    new.SetPosition(old.GetPosition())
    b.Add(new)
    before = {p.GetNumber(): p for p in old.Pads()}
    for p in new.Pads():
        q = before[p.GetNumber()]
        assert p.GetPosition() == q.GetPosition(), (p.GetNumber(), p.GetPosition(), q.GetPosition())
        p.SetNet(q.GetNet()); p.SetPinFunction(q.GetPinFunction()); p.SetPinType(q.GetPinType())
    copy_text(old.Reference(), new.Reference())
    copy_text(old.Value(), new.Value())
    b.Remove(old)
    return old, was                                  # keep it referenced until the script ends


def main():
    kept = {f: f.read_bytes() for f in PROJECT if f.exists()}   # SaveBoard rewrites them
    b = pcb.LoadBoard(str(BOARD))
    gone, was = swap_footprint(b)
    stale = make_r1_pcb.mark_j5(b)
    pcb.SaveBoard(str(BOARD), b)
    b = pcb.LoadBoard(str(BOARD))
    pcb.ZONE_FILLER(b).Fill(b.Zones())
    pcb.SaveBoard(str(BOARD), b)
    for f, data in kept.items():
        f.write_bytes(data)
    b.BuildConnectivity()
    print('unconnected:', b.GetConnectivity().GetUnconnectedCount(True))

    for path, old, new in ((SCH, f'"{was[0]}:{was[1]}"', f'"{NEW[0]}:{NEW[1]}"'),
                           (BOM, f'"{was[1]}"', f'"{NEW[1]}"')) if was else ():
        t = path.read_bytes()
        assert t.count(old.encode()) == 1, (path.name, t.count(old.encode()))
        path.write_bytes(t.replace(old.encode(), new.encode()))
    mod = KICAD / f'{OLD[0][0]}.pretty' / f'{OLD[0][1]}.kicad_mod'
    if mod.exists():
        mod.unlink()
    print('J5 is now', ':'.join(NEW))
    del gone, stale


if __name__ == '__main__':
    main()
