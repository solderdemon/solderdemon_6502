"""Route the r5 board's signals, keeping the r4 placement, power copper and planes, then tidy up.

Run with KiCad's python, after make_r5_pcb.py:

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/route_r5.py
    ... tools/route_r5.py --import-only      # reuse .routing/routing.ses on a fresh make_r5_pcb.py board

Uses the workspace's shared router (../tools/route_swarm.py, Freerouting 2.4.x, several variants
at once, each result DRC-checked by KiCad).

Every signal is routed afresh. Adding only the missing connections to the kept r4 copper was tried
first and does not converge: with the r4 tracks fixed around the new socket, Freerouting was still
at 45 unrouted connections after eight passes, where a clean start was at 5 after six. What stays
from r4 is the placement, the VCC/GND planes on In1/In2 and the few VCC/GND tracks. In the .dsn the
inner layers become power layers, so no signal is routed through a plane.

The four pad-less silkscreen logos stay out of the .dsn: two of them share the reference REF**,
and KiCad's Specctra export refuses that.

Environment: ROUTE_MODE=best|fast|single (default best: the r4 board already carries one DRC
error, a courtyard overlap of U3 and JP3, so no candidate ever looks clean enough for 'fast');
ROUTE_JOBS=n caps the parallel routers (default: route_swarm sizes it to the cores).
"""
from pathlib import Path
import os, re, shutil, subprocess, sys
import pcbnew as pcb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_r5_pcb import BOARD, PROJECT, POWER, erode  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.routing'
SHARED = ROOT.parent / 'tools'                               # route_swarm.py, validate_ses.py, jar
PLANES = ('In1.Cu', 'In2.Cu')


def copper_text_keepouts(b):
    """Specctra keepouts over the copper texts (the 'r5' in the top left corner): KiCad does not
    export text to the .dsn, so without these Freerouting runs tracks straight through it."""
    out = []
    for d in b.GetDrawings():
        if isinstance(d, pcb.PCB_TEXT) and d.IsOnCopperLayer():
            bb = d.GetBoundingBox(); bb.Inflate(pcb.FromMM(0.3))
            x1, y1, x2, y2 = (round(pcb.ToMM(v) * 1000) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
            layer = b.GetLayerName(d.GetLayer())
            out.append(f'    (keepout "" (polygon {layer} 0  {x1} {-y1}  {x2} {-y1}  {x2} {-y2}  {x1} {-y2}  {x1} {-y1}))')
    return out


def prepare_dsn(text, keepouts=()):
    """Inner layers are planes, not routing layers; only power copper is carried over."""
    for layer in PLANES:
        text = text.replace(f'(layer {layer}\n      (type signal)', f'(layer {layer}\n      (type power)')
    if keepouts:
        i = text.index('    (via "', text.index('(structure'))       # the structure's via rule
        text = text[:i] + '\n'.join(keepouts) + '\n' + text[i:]
    head, wiring = text[:text.index('(wiring')], text[text.index('(wiring'):]
    power = '|'.join(re.escape(n) for n in POWER)
    kept = [l for l in wiring.split('\n')
            if not re.match(r'\s*\((wire|via)\b', l) or re.search(rf'\(net ({power})\)', l)]
    return head + '\n'.join(kept)


def route():
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(exist_ok=True)                                # rmtree fails quietly on a busy dir
    dsn, ses = WORK / 'routing.dsn', WORK / 'routing.ses'

    copy = WORK / BOARD.name
    shutil.copyfile(BOARD, copy)
    b = pcb.LoadBoard(str(copy))
    for f in [f for f in b.GetFootprints() if len(f.Pads()) == 0]:
        b.Delete(f)
    assert pcb.ExportSpecctraDSN(b, str(dsn)), 'Specctra export failed'
    text = prepare_dsn(dsn.read_text(encoding='utf-8'), copper_text_keepouts(b))
    dsn.write_text(text, encoding='utf-8')
    print(f'{dsn.name}: {text.count("(type power)")} plane layers, '
          f'{len(re.findall(r"^[ ]*[(](?:wire|via)[ ]", text, re.M))} power wires/vias kept')

    subprocess.run([sys.executable, str(SHARED / 'route_swarm.py'), str(dsn), str(ses),
                    '--board', str(BOARD), '--mode', os.environ.get('ROUTE_MODE', 'best'),
                    '--workdir', str(WORK / 'swarm'), '--jobs', os.environ.get('ROUTE_JOBS', '0')], check=True)


def main():
    kept = {f: f.read_bytes() for f in PROJECT if f.exists()}
    if '--import-only' not in sys.argv:
        route()
    b = pcb.LoadBoard(str(BOARD))
    # KiCad 10 adds the session to whatever is on the board rather than replacing it, so the old
    # signal tracks go first. The power copper stays: Freerouting does not hand back fixed wiring
    # on nets it treats as planes, so the session has none of it.
    for t in [t for t in b.GetTracks() if t.GetNetname() not in POWER]:
        b.Delete(t)
    assert pcb.ImportSpecctraSES(b, str(WORK / 'routing.ses')), 'session import failed'
    # Freerouting leaves stubs where it tore a trace up; erode them like make_r5_pcb.py does
    nets = {t.GetNetname() for t in b.GetTracks()} - POWER
    print('stubs removed:', erode(b, nets))
    for t in b.GetTracks():                                  # hand it back editable, like r4 was
        t.SetLocked(False)
    pcb.ZONE_FILLER(b).Fill(b.Zones())
    pcb.SaveBoard(str(BOARD), b)
    for f, data in kept.items():
        f.write_bytes(data)
    b.BuildConnectivity()
    print('tracks+vias:', len(b.GetTracks()), ' unrouted connections:',
          b.GetConnectivity().GetUnconnectedCount(True))


if __name__ == '__main__':
    main()
