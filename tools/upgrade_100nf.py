"""Rebuild the current r1 host placement with 5.08 mm 100 nF capacitors.

The compressed placement snapshot preserves the reviewed host layout that
followed the original make_r1_pcb.py build. Run this with KiCad's Python, then
run route_r5.py to redraw signal tracks around the larger capacitors.
"""
import gzip
from pathlib import Path
import sys
import tempfile

import pcbnew as pcb
import wx

wx.Log.EnableLogging(False)
ROOT = Path(__file__).resolve().parents[1]
KICAD = ROOT / 'design'
NAME = 'solderdemon_6502'
BOARD = KICAD / f'{NAME}.kicad_pcb'
SCH = KICAD / f'{NAME}.kicad_sch'
PROJECT = KICAD / f'{NAME}.kicad_pro'
SNAPSHOT = ROOT / 'design' / 'placement_before_5mm_caps.kicad_pcb.gz'
sys.path.insert(0, str(ROOT.parent / 'tools' / 'capacitors'))
from replace import replace_100nf


def mm(x, y):
    return pcb.VECTOR2I(pcb.FromMM(x), pcb.FromMM(y))


def place_cap_references(board):
    """Keep each 100 nF designator inside its own silkscreen body outline."""
    caps = [f for f in board.GetFootprints() if f.GetValue() == '100nF']
    assert len(caps) == 10, [f.GetReference() for f in caps]
    for cap in caps:
        assert cap.GetFPIDAsString() == 'SolderDemonCaps:C_Radial_5.08mm'
        cap.Reference().SetPosition(cap.GetPosition())
        cap.Reference().SetTextAngleDegrees(cap.GetOrientationDegrees())


def align_crystal_cap_references(board):
    """Centre C13 and C14 on a shared baseline just below their outlines."""
    for ref in ('C13', 'C14'):
        cap = board.FindFootprintByReference(ref)
        assert cap is not None and cap.GetValue() == '7pF'
        origin = cap.GetPosition()
        cap.Reference().SetPosition(pcb.VECTOR2I(origin.x, origin.y + pcb.FromMM(6.275)))
        cap.Reference().SetTextAngleDegrees(0)
        cap.Reference().SetHorizJustify(pcb.GR_TEXT_H_ALIGN_CENTER)


def update_production(board, refs):
    production = ROOT / 'manufacturing'
    bom = production / 'bom.csv'
    if bom.is_file():
        source = bom.read_text(encoding='utf-8')
        old = 'C_Rect_L4.0mm_W2.5mm_P2.50mm'
        if old in source:
            assert source.count(old) == 1
            bom.write_text(source.replace(old, 'C_Radial_5.08mm'), encoding='utf-8')
    positions = production / 'positions.csv'
    if positions.is_file():
        by_ref = {}
        for ref in refs:
            f = board.FindFootprintByReference(ref)
            x, y = f.GetPosition().x, f.GetPosition().y
            by_ref[ref] = (pcb.ToMM(x), -pcb.ToMM(y), f.GetOrientationDegrees())
        updated = []
        for line in positions.read_text(encoding='utf-8').splitlines():
            ref = line.split(',', 1)[0]
            if ref in by_ref:
                x, y, angle = by_ref[ref]
                line = f'{ref},{x:.4f},{y:.4f},{angle:.1f},top'
            updated.append(line)
        positions.write_text('\n'.join(updated) + '\n', encoding='utf-8')


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--markings-only':
        board = pcb.LoadBoard(str(BOARD))
        place_cap_references(board)
        align_crystal_cap_references(board)
        pcb.SaveBoard(str(BOARD), board)
        print('aligned capacitor references')
        return
    if len(sys.argv) > 1 and sys.argv[1] == '--production-only':
        board = pcb.LoadBoard(str(BOARD))
        refs = [f.GetReference() for f in board.GetFootprints() if f.GetValue() == '100nF']
        assert len(refs) == 10, refs
        update_production(board, refs)
        print('updated production BOM and positions')
        return
    output = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else BOARD
    kept_project = PROJECT.read_bytes()
    with tempfile.TemporaryDirectory(dir=ROOT / 'design') as directory:
        source = Path(directory) / f'{NAME}.kicad_pcb'
        source.write_bytes(gzip.decompress(SNAPSHOT.read_bytes()))
        board = pcb.LoadBoard(str(source))
        refs, removed = replace_100nf(board)
        assert len(refs) == 10, refs
        # C2 and C3 would have opposite-net pads 1.49 mm apart.
        board.FindFootprintByReference('C3').Move(mm(1, 0))
        # C11's wider body needs more space below U1.
        board.FindFootprintByReference('C11').Move(mm(0, 2))
        place_cap_references(board)
        align_crystal_cap_references(board)
        pcb.ZONE_FILLER(board).Fill(board.Zones())
        pcb.SaveBoard(str(output), board)
    if PROJECT.read_bytes() != kept_project:
        PROJECT.write_bytes(kept_project)

    if output != BOARD:
        print('placed', ', '.join(sorted(refs)), 'in', output)
        return

    old = 'Capacitor_THT:C_Rect_L4.0mm_W2.5mm_P2.50mm'
    source = SCH.read_text(encoding='utf-8')
    if old in source:
        assert source.count(old) == 10
        SCH.write_text(source.replace(old, 'SolderDemonCaps:C_Radial_5.08mm'), encoding='utf-8')
    table = KICAD / 'fp-lib-table'
    source = table.read_text(encoding='utf-8')
    if '(name "SolderDemonCaps")' not in source:
        source = source.replace('\n)', '\n  (lib (name "SolderDemonCaps")(type "KiCad")(uri "${KIPRJMOD}/SolderDemonCaps.pretty")(options "")(descr "5.08 mm radial capacitor"))\n)')
        table.write_text(source, encoding='utf-8')
    update_production(board, refs)
    print('placed', ', '.join(sorted(refs)))


if __name__ == '__main__':
    main()
