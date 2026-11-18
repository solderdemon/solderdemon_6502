"""Rename the project's symbol and footprint library from rosco_6502 to solderdemon_6502.

The r1 generators start from boards and schematics committed while the library still had its
rosco_6502 name, so make_r1_pcb.py calls this at the end; it can also run on its own. Renames
design/rosco_6502.kicad_sym and rosco_6502.pretty, the two library tables, every
"rosco_6502:" library reference and the stale "rosco_6502.kicad_sch" sheet file on the
footprints. Copper is untouched. Safe to run again.

    python tools/rename_lib.py
"""
from pathlib import Path

KICAD = Path(__file__).resolve().parent.parent / 'design'
OLD, NEW = 'rosco_6502', 'solderdemon_6502'
PROJECT = 'solderdemon_6502'


def main():
    for suffix in ('.kicad_sym', '.pretty'):
        old, new = KICAD / f'{OLD}{suffix}', KICAD / f'{NEW}{suffix}'
        if old.exists():
            assert not new.exists(), f'both {old.name} and {new.name} exist'
            old.rename(new)
    changes = {
        'sym-lib-table': [(f'(name "{OLD}")', f'(name "{NEW}")'), (f'/{OLD}.kicad_sym', f'/{NEW}.kicad_sym')],
        'fp-lib-table': [(f'(name "{OLD}")', f'(name "{NEW}")'), (f'/{OLD}.pretty', f'/{NEW}.pretty')],
        f'{PROJECT}.kicad_sch': [(f'"{OLD}:', f'"{NEW}:')],
        f'{PROJECT}.kicad_pcb': [(f'"{OLD}:', f'"{NEW}:'), (f'"{OLD}.kicad_sch"', f'"{PROJECT}.kicad_sch"')],
    }
    for name, pairs in changes.items():
        path = KICAD / name
        text = path.read_bytes().decode('utf-8')      # keep the line endings as they are
        new = text
        for a, b in pairs:
            new = new.replace(a, b)
        if new != text:
            path.write_bytes(new.encode('utf-8'))
            print('renamed library references in', name)


if __name__ == '__main__':
    main()
