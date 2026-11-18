# Board preview assets

The images in this directory are generated from `design/solderdemon_6502.kicad_pcb`. J1, J2 and J3 are straight pin headers. `solderdemon-logo.png` is the source of the SolderDemon logo footprint (`tools/make_logo.py`).

Use KiCad 10 and its standard 3D model library from the repository root:

```sh
kicad-cli pcb render --side top -w 1600 -h 1600 --output images/solderdemon_6502-top.png design/solderdemon_6502.kicad_pcb
kicad-cli pcb render --side bottom -w 1600 -h 1600 --output images/solderdemon_6502-bottom.png design/solderdemon_6502.kicad_pcb
kicad-cli pcb render --side top --rotate '-35,0,45' --zoom 0.7 -w 1800 -h 1400 --output images/solderdemon_6502-board-3d.png design/solderdemon_6502.kicad_pcb
```

The local PLCC-44 socket model is illustrative, not a mechanical clearance specification. The colours and bodies of other generic models may differ from purchased parts. `tools/render_board.py` is retained as an optional custom visualizer but is not used for the checked-in images.
