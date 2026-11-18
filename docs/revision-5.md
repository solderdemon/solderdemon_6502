# Revision 5 notes (SolderDemon 6502 r1)

[Documentation index](README.md)

r5 is released as **SolderDemon 6502 r1**, the first SolderDemon revision: the same design, with
the KiCad project renamed to `solderdemon_6502` and the SolderDemon identity on the board (see
[Identity](#identity)). The notes below keep the name r5 for the design work.

These are historical design notes. The current r1 [layout](layout-r1.md) moves the parts and
removes the standalone J4/CS2 pin header.

r5 is r4 with its glue logic moved into one ATF1502AS-10JU44 CPLD. The CPU, memory map, memories,
DUART, bank register, connectors and firmware are unchanged. The r5 design files have been checked
by simulation and design rules only: **no r5 board has been built yet**.

## What changed

| r4 | r5 |
| --- | --- |
| IC2: ATF22V10C address decoder (DIP-24) | IC2: ATF1502AS-10JU44 CPLD in a PLCC-44 socket; decoder, glue and reset generator in one chip |
| IC5: ATF22V10C glue logic (DIP-24) | Removed; its logic is in IC2 |
| IC4: NE555 reset timer with C19, C20 and R9 | Removed; IC2 generates the power-on and button reset |
| PLDs programmed in a TL866/T48 out of the board | J8, a 10-pin JTAG header: IC2 is programmed in place |
| S1 (RESET) in the middle of the board | S1 on the bottom edge, next to the LEDs; J8 beside it |
| Lower half packed around the two GALs and the 555 | Spread out into the freed space: IC2 right under the memories, U4 lying under it, R7/R8/R11 in a row by the power jack, LED1–LED2–RESET–JTAG evenly spaced along the bottom edge |
| R8 2K2, the 555 timing resistor | R8 3K3, S1's pull-up, the same value as every other pull-up |
| J3 (SPI / SD card header): pin 1 (CS) at the top, GND at the bottom | J3 turned round: GND at the top, pin 1 (CS) at the bottom next to J4 (CS2). Same pinout, CS–CK–COPI–CIPO–VCC–GND from pin 1 |

Five parts fewer (IC4, IC5, C19, C20, R9) and one more (J8). C8 and C12, the r4 decoupling for the
two GALs, now decouple IC2.

## IC2: ATF1502AS

Source: [code/firmware/pld/cpld/ic2_glue.pld](../code/firmware/pld/cpld/ic2_glue.pld) (CUPL). The fitter report
[ic2_glue.fit](../code/firmware/pld/cpld/ic2_glue.fit) lists the final pinout; the design uses 29 of 32
macrocells and 28 of 32 I/O pins, with JTAG left enabled.

| Function | Pins |
| --- | --- |
| A1–A15 in (A0 is not decoded) | 17–21, 24–29, 31, 33, 34, 36 |
| PHI2 (GCLK1), R/W (OE2), /DUADTACK (OE1), /RSTBTN (GCLR) | 43, 2, 44, 1 |
| /RESET, RDY (open drain) | 4, 5 |
| /DUASEL, /LOWRAM, /BANKRAM, /ROMOE, /RD, /WR, BANKCLK | 6, 8, 9, 11, 12, 14, 16 |
| JTAG: TDI, TMS, TCK, TDO | 7, 13, 32, 38 |
| Spare, not connected | 37, 39, 40, 41 |

The address decoder and glue equations are copied from the r4 GAL sources. The block split matters:
all nine outputs sit in logic block A so that the reset counter's upper bits land in block B. With
the outputs in block B the fitter runs out of input routing ("Fail to route variable A3").

### Reset

A 19-bit counter clocked by PHI2 holds /RESET low for 2^18 clocks after power-up and after S1 is
released: 19 ms at 14 MHz, 26 ms at 10 MHz, 0.26 s at 1 MHz (the r4 555 gave about 24 ms). The
ATF1502AS clears its registers at power-up, and S1 clears the counter asynchronously, so contact
bounce only restarts the count. Without a clock there is no end of reset: the 65C02 is never
released before X1 runs. /RESET stays open drain with R7 as its pull-up, so an expansion card can
still pull it.

### Timing

The ATF1502AS-10 has a 10 ns pin-to-pin delay; the r4 ATF22V10C-7 had 7.5 ns.

- Signals that crossed both GALs get faster, from 2 × 7.5 ns to 10 ns: /ROMOE, RDY (from the
  DUART decode) and BANKCLK (from the address).
- Signals that crossed one GAL get slower, from 7.5 ns to 10 ns: /LOWRAM, /BANKRAM and /DUASEL
  (address to select), /RD, /WR and BANKCLK (from PHI2).

The 2.5 ns lost on the RAM selects comes out of the RAM access budget. This has not been worked
through against the datasheets: check it on the first board at the highest clock you intend to run.

BANKCLK keeps the r4 behaviour: two pulses per write to `$0000/$0001`. The 74HCT174 stores the
second pulse, whose rising edge now follows PHI2's fall by up to 10 ns instead of 7.5 ns. That edge
relies on the 65C02's data hold time after PHI2. Check it on the first board too. If either
margin turns out too small, an ATF1502AS-7 (7.5 ns) is a drop-in replacement and restores the r4
timing on every path.

## How it was checked

| Check | Result |
| --- | --- |
| [tools/check_cpld.py](../tools/check_cpld.py): r5 CUPL equations against the r4 JEDEC fuse maps (two GALs chained as on the board) | 262 144 input combinations, 0 differences |
| Same script: reset counter from power-up, then S1 with bounce | 262 144 clocks both times; bounce holds reset |
| WinCUPL + Atmel fitter ([build.sh](../code/firmware/pld/cpld/build.sh)) | Fits, pinout as assigned, JTAG on |
| KiCad ERC | 0 errors; the warnings are the ones r4 already had |
| KiCad DRC with schematic parity | See [the board section](#board) |

## Board

The r5 schematic and board are derived from r4 by scripts, not edited by hand, so they can be
regenerated at any time:

```sh
K="/c/Program Files/KiCad/10.0/bin"
python tools/make_r5_sch.py                 # r4 schematic from git -> r5 schematic + symbol library
"$K/python.exe" tools/make_r5_pcb.py        # r4 board from git -> r5 placement and nets
"$K/python.exe" tools/route_r5.py           # Freerouting: every signal routed afresh
"$K/python.exe" tools/brand_r1.py           # SolderDemon identity, revision r1
```

The upper half of the placement (CPU, memories, J5), the VCC/GND planes on In1/In2 and the
VCC/GND tracks come from r4; the lower half is re-placed (`PLACE` in `make_r5_pcb.py`). Every
signal track is new. Keeping the hand-routed r4 signals and adding only the missing connections was tried
first and did not converge: with the r4 tracks fixed around the new socket, Freerouting was still
at 45 unrouted connections after eight passes, where a clean start was at 5 after six and at 0
after nine. The inner layers are declared as planes for the router, so no signal crosses them (r4
had 34 hand-routed signal segments on In1/In2).

## Identity

`tools/brand_r1.py` runs last, on the routed board, and changes only silkscreen and the copper
revision mark, so the routing stays valid:

- the rosco_6502 logotype at the top edge, the open hardware logo and the RoHS logo are gone;
  "SolderDemon 6502" stands in the logotype's place;
- the SolderDemon pixel-art logo is on the back, between the 65C02's rows of pins (the only place
  with 12 mm to spare), with "SolderDemon" and "solderdemon_6502 r1" under it. The footprint is
  `solderdemon_6502:SolderDemon_Logo`, made from `images/solderdemon-logo.png` by
  `tools/make_logo.py` (the busboard's generator, 12.8 mm high);
- the copper mark in the top left corner reads r1 and the back carries "(c)2026 SolderDemon";
- the schematic and board title blocks read "Copyright (c)2026 SolderDemon", with one line
  "Modified 2026-09-30 from rosco_6502 r4, (c)2022-2023 Ross Bamford & Contributors": CERN OHL
  v1.2 (3.1, 3.4b) asks for the original notice and a modification notice in the design files,
  not on the board.

The KiCad symbol and footprint library is `solderdemon_6502` (`design/solderdemon_6502.kicad_sym`,
`solderdemon_6502.pretty`). The r4 base files still call it `rosco_6502`; `tools/rename_lib.py`, run at
the end of `make_r1_pcb.py`, renames it.

`route_r5.py` uses the workspace's shared router (`../tools/route_swarm.py`) and needs Java 25 and
Freerouting 2.4.1 in `../tools`.

## Programming IC2

J8 follows the 10-pin Altera ByteBlaster layout that Microchip's (Atmel's) ATDH1150USB cable uses:

| Pin | Signal | Pin | Signal |
| --- | --- | --- | --- |
| 1 | TCK | 2 | GND |
| 3 | TDO | 4 | VCC |
| 5 | TMS | 6 | — |
| 7 | — | 8 | — |
| 9 | TDI | 10 | GND |

Program `code/firmware/pld/cpld/ic2_glue.jed`, for example with an ATDH1150USB and Microchip's ATMISP.
ATMISP can also write an SVF file for any JTAG adapter that plays SVF. See
[PLD firmware](pld-firmware.md#r5-ic2-atf1502as).

**First programming:** do it with only IC2 in its socket. A blank ATF1502AS drives none of the
chip selects, while R7 lets the 65C02 run, so with the other chips fitted the memories could
fight over the data bus. For later reprogramming, hold the CPU in reset by connecting /RESET
(J5 pin 10) to GND (J5 pin 6). /RESET is open drain, so this is safe.
