"""Export the routed r1 board's Gerbers, drills and a ready-to-upload ZIP."""

from pathlib import Path
import json
import os
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'design/solderdemon_6502.kicad_pcb'
CAM = ROOT / 'manufacturing/gerbers'
ZIP = ROOT / 'manufacturing/solderdemon_6502-r1-gerbers.zip'
PRODUCTION_ZIP = ROOT / 'manufacturing/SolderDemon_6502_Mainboard_r1.zip'
CLI = os.environ.get('KICAD_CLI', 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')
STEM = BOARD.stem
LAYERS = ('F_Cu', 'In1_Cu', 'In2_Cu', 'B_Cu', 'F_Paste', 'B_Paste',
          'F_Silkscreen', 'B_Silkscreen', 'F_Mask', 'B_Mask', 'Edge_Cuts')
EXPECTED = {f'{STEM}-{layer}.gbr' for layer in LAYERS}
EXPECTED |= {f'{STEM}-PTH.drl', f'{STEM}-NPTH.drl', f'{STEM}-job.gbrjob'}


def main():
    CAM.mkdir(exist_ok=True)
    subprocess.run([CLI, 'pcb', 'export', 'gerbers', '--board-plot-params',
                    '-o', str(CAM) + os.sep, str(BOARD)], check=True)
    subprocess.run([CLI, 'pcb', 'export', 'drill', '--excellon-separate-th',
                    '-o', str(CAM) + os.sep, str(BOARD)], check=True)
    missing = EXPECTED - {path.name for path in CAM.iterdir()}
    assert not missing, f'missing manufacturing files: {sorted(missing)}'
    job = json.loads((CAM / f'{STEM}-job.gbrjob').read_text(encoding='utf-8'))
    specs = job['GeneralSpecs']
    assert specs['LayerNumber'] == 4 and specs['BoardThickness'] == 1.6, specs
    with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(EXPECTED):
            archive.write(CAM / name, name)
    shutil.copyfile(ZIP, PRODUCTION_ZIP)
    print(f'{ZIP}: {len(EXPECTED)} files, four layers, 1.6 mm')


if __name__ == '__main__':
    main()
