# SolderDemon 6502 Documentation

SolderDemon 6502 is an open single-board computer built around the WDC 65C02, with banked memory, two UARTs and SD access over SPI. It is based on rosco_6502. This guide covers the rosco_6502 r4 board, the SolderDemon 6502 r1 design (developed as r5, not built yet; "r5" below means r1) and the current ca65 firmware in this repository.

## Where to start

| Task | Guide |
| --- | --- |
| Power up the board and connect a terminal | [Getting started](getting-started.md) |
| Check power connections, ROM options and memory layout | [Hardware](hardware.md) |
| Build and program the EEPROM | [ROM firmware](rom-firmware.md) |
| Build JEDEC files and program IC2 and IC5 (r4) or the IC2 CPLD over JTAG (r5) | [PLD firmware](pld-firmware.md) |
| Build a program and load it over UART or from SD | [Software development](software.md) |
| Build and run a program with the rosco CLI, with or without the board | [rosco CLI and emulator](software.md#rosco-cli-and-emulator) |
| Diagnose a failure | [Troubleshooting](troubleshooting.md) |
| Read the manufacturer's r4 notices | [Revision 4 notes](revision-4.md) |
| See what r5 changes: one ATF1502AS CPLD, JTAG, reset button on the edge | [Revision 5 notes](revision-5.md) |
| See the r1 placement and rebuild steps | [r1 layout](layout-r1.md) |

For a new board, follow this sequence: inspect assembly and power connections → program both PLDs (r4), or program IC2 over JTAG with only IC2 fitted (r5) → program ROM → start with a terminal → load a RAM program.

## Repository layout

| Directory | Contents |
| --- | --- |
| [design](../design) | Schematic, PCB, symbol and footprint libraries, component CSV |
| [manufacturing/gerbers](../manufacturing/gerbers) | Gerber and drill files |
| [code/firmware/pld](../code/firmware/pld) | Logic equations, JEDEC files and programming scripts (r4 GALs, r5 CPLD) |
| [tools](../tools) | Generators and checks: schematic, board, r1 placement, routing, CPLD equivalence |
| [code/firmware](../code/firmware) | Main ca65 firmware |
| [code/software](../code/software) | Examples and filesystem utilities |

## Status and sources

The firmware is under development. FAT32 support is read-only; an API symbol does not necessarily identify an implemented function. Known limitations are documented in the ROM and troubleshooting guides.

Commands follow the Makefiles and scripts in this repository. Run `sh` blocks in Bash. On Windows, use an environment providing Bash, GNU Make and the required tools on PATH. Validate builds and physical programming in your own environment.

The former `r4 Information.docx` and `r4 Information.pdf` are replaced by [Revision 4 notes](revision-4.md), with technical details also included in the relevant guides. The schematic PDF in `design` remains a drawing.

## Licences

- Software: MIT, see [LICENSE](../LICENSE).
- Hardware: CERN Open Hardware Licence, see [LICENCE.hardware.txt](../LICENCE.hardware.txt).
- Documentation: [Creative Commons Attribution 2.0 UK](https://creativecommons.org/licenses/by/2.0/uk/), as stated in the project README.
- Original project authors: Ross Bamford and contributors. The r4 notice was issued by The Really Old-School Company Limited.

[Back to the project README](../README.md)
