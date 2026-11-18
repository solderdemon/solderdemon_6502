# Hardware and memory map

[Documentation index](README.md)

## Main components

| Component | Purpose |
| --- | --- |
| WDC 65C02 | CPU |
| SCN68681C1A44 | Two UARTs, timer, GPIO for SPI and indicators |
| 16 KiB low RAM | Permanently mapped memory, stack and system structures |
| 16 × 32 KiB RAM | Banked memory; 528 KiB total including low RAM |
| AT28C64B or AT28C256 | 8 KiB ROM or four 8 KiB banks |
| IC2 | r4: address decoder PLD (ATF22V10C). r5: ATF1502AS CPLD with the decoder, glue logic and reset generator |
| IC5 | r4 only: glue logic PLD (ATF22V10C) |
| IC4 | r4 only: NE555 reset timer; r5 generates reset in IC2 |
| J8 | r5 only: JTAG header for programming IC2 in the board |

The original README specifies up to 14 MHz in theory, with 10 MHz as the testing target. This does not guarantee that every combination of components will operate at that frequency.

The current board uses an SCN68681C1A44 DUART, with the console configured for 38400 bit/s. Older design files and source comments may still refer to the previous XR68C681 device; check them against the populated board.

## CPU address space

| CPU addresses | Window size | Purpose |
| --- | --- | --- |
| `$0000–$3FFF` | 16 KiB | Low RAM; writes at the beginning also control banking |
| `$4000–$BFFF` | 32 KiB | Selected RAM bank, 0–15 |
| `$C000–$C00F` | 16 bytes | DUART registers |
| `$C010–$DFFF` | Remaining I/O | Reserved I/O space |
| `$E000–$FFFF` | 8 KiB | ROM; one of four banks with an AT28C256 |

`BANK_SET = $0000`: bits 0–3 select RAM and bits 4–5 select ROM. Preserve the ROM bits when changing the RAM bank. Do not switch banks while executing in the affected window without a deliberately arranged transition.

The headers reserve `$0001` as `BANK_RSVD`, but the IC2 equation decodes both `$0000/$0001`. Do not use either address as an ordinary variable. Reads return the contents of the underlying RAM.

## System RAM

| Range | Usage |
| --- | --- |
| `$0002–$000F` | Firmware zero page |
| `$0010–$001F` | Filesystem zero page according to the constants |
| `$0020–$002F` | Monitor zero page according to the constants |
| `$0030–$003F` | Avoid in portable examples: comments and constants disagree |
| `$0040–$00FF` | Application zero page in the example linker configurations |
| `$0100–$01FF` | CPU stack |
| `$0200–$023F` | Firmware variables and reserved space |
| `$0240–$029F` | RAM vector area |
| `$02A0–$02FF` | ROM switching helper code |
| `$0300–$03FF` | Input buffer |
| `$0400–$05FF` | Filesystem sector buffer |
| `$0600–$06FF` | Filename buffer |
| `$0700–$07FF` | Scratch buffer / bank copying |
| `$0800–$3FFF` | 14 KiB low RAM for applications |

The introductory table in `defines.inc` disagrees with the constants about zero page and the RAM vector boundaries. The vector boundaries above follow the linker configuration. The conservative application zero-page start follows the example configurations (`$0040`).

## Board design files

- [KiCad schematic](../design/solderdemon_6502.kicad_sch), [PDF schematic](../manufacturing/solderdemon_6502-schematic.pdf). The KiCad files are SolderDemon 6502 r1 (developed as r5); the rosco_6502 r4 files are in git history (commit `febedf81d62ee84a51998f37c9de908616646e20`).
- [PCB](../design/solderdemon_6502.kicad_pcb), [KiCad project](../design/solderdemon_6502.kicad_pro).
- [Component CSV](../design/solderdemon_6502.csv), [manufacturing files](../manufacturing/gerbers).
- [Firmware constants](../code/firmware/inc/defines.inc), [ROM linker configuration](../code/firmware/rosco_6502_32K.cfg).

The Gerbers and drill files in `manufacturing/gerbers` are exported from the r1 board (see [r1 notes](revision-5.md)); the r4 Gerbers are in git history. The r4 GAL source headers say r1: that is an upstream rosco_6502 revision number, not SolderDemon r1.