# Building and programming PLDs

[Documentation index](README.md)

The PLDs implement hardware logic. Their JEDEC files are programmed separately from the EEPROM; building ROM does not update the PLDs.

r5 boards have one ATF1502AS CPLD (IC2) instead of the two r4 GALs and the 555. See the next section. The rest of this page covers r4.

## r5: IC2 (ATF1502AS)

| Position | Function | Directory | Programming file |
| --- | --- | --- | --- |
| IC2 | Address decoder, glue logic and reset generator | [cpld](../code/pld/cpld) | `ic2_glue.jed` |

The source is CUPL (`ic2_glue.pld`). It needs WinCUPL and Atmel's fitter; the
[`dinoboards/cpld-toolchain`](https://codeberg.org/dinoboards/cpld-toolchain) Docker image bundles both:

```sh
bash code/pld/cpld/build.sh          # -> ic2_glue.jed and ic2_glue.fit
python tools/check_cpld.py           # equations against the r4 GAL fuses, and the reset counter
```

`build.sh` fails unless the fitter reports that the design fits with JTAG enabled. `check_cpld.py`
needs only Python 3. It compares the CUPL equations, input for input, with the r4 JEDEC files in
`address_decoder/` and `glue/`, and it steps the reset counter through power-up and a bouncing
button press. Run both after every change to the equations.

Program IC2 in the board through J8, the JTAG header (10-pin Altera/ATDH1150USB layout, pin 1 =
TCK). With Microchip's ATDH1150USB cable, load `ic2_glue.jed` in ATMISP. ATMISP can also write an
SVF file for other JTAG adapters.

- **First programming:** fit only IC2, then program it. A blank CPLD drives none of the chip
  selects, and the 65C02 is not held in reset.
- **Reprogramming:** connect J5 pin 10 (/RESET) to J5 pin 6 (GND) first, so the CPU stays in reset
  while the CPLD's outputs are frozen.

The TL866/T48 route used for the GALs below does not apply to IC2.

## r4: device and file mapping

| Position | Function | Directory | Programming file |
| --- | --- | --- | --- |
| IC2 | Address decoder | [address_decoder](../code/pld/address_decoder) | `ic2_address_decoder.jed` |
| IC5 | Glue logic | [glue](../code/pld/glue) | `ic5_glue_logic.jed` |

Both `burn.sh` scripts use the `ATF22V10C(UES)` profile. The source files specify the `GAL22V10` architecture; this does not mean any GAL is a suitable replacement for the actual device. Check the chip markings and your board schematic.

## Files and tools

- `.pld`: source equations and pin assignments.
- `.jed`: JEDEC data for the programmer.
- `.pin`, `.chp`, `.fus`: pin, package and fuse-array reports.
- `burn.sh`: programs an existing JEDEC file without compiling it.

The checked-in JEDEC headers identify **GALasm 2.1**. Rebuilding requires GALasm. Programming requires Bash, minipro and a compatible programmer. See the [GALasm documentation](https://github.com/daveho/GALasm#readme) for syntax and options.

## Rebuild after changing the logic

From the repository root, build each PLD separately:

```sh
cd code/pld/address_decoder
galasm ic2_address_decoder.pld
```

```sh
cd code/pld/glue
galasm ic5_glue_logic.pld
```

The second block also starts from the repository root. The executable name depends on your installation: use `GALasm` instead of `galasm` if that is its name.

Compilation must finish without errors and generate the corresponding `.jed`. Review the pin reports and run `git diff -- code/pld` from the repository root to inspect changes. Do not program after a failed build: an older JEDEC file may still be present. This repository has no separate PLD Makefile.

If the equations have not changed, you can use the checked-in JEDEC files after confirming the board revision and device assignments.

## r4: program IC2

With board power disconnected, remove IC2 and insert it into the programmer according to its placement instructions. From the repository root:

```sh
cd code/pld/address_decoder
bash burn.sh
```

The script executes:

```sh
minipro -p 'ATF22V10C(UES)' -w ic2_address_decoder.jed
```

## r4: program IC5

Insert IC5 into the programmer separately. From the repository root:

```sh
cd code/pld/glue
bash burn.sh
```

The equivalent command is:

```sh
minipro -p 'ATF22V10C(UES)' -w ic5_glue_logic.jed
```

Quotes protect the parentheses in the device profile from Bash interpretation. The scripts use relative paths, so run each from its own directory.

After each operation, confirm that writing and verification completed successfully. Label the devices IC2 and IC5 to avoid mixing them up, then reinstall them in the correct orientation with board power disconnected.

## What the equations implement

IC2 selects low RAM, banked RAM, I/O, ROM, the DUART and the bank register. `BANKSEL` is active high; both `$0000` and `$0001` activate it.

IC5 generates `RD`, `WR`, `BANKCLK` and two ROM output-enable signals, and controls `RESET` and `RDY`. The source comment explains the two `BANKCLK` pulses during a write: an intermediate incorrect value is replaced by the correct value before banked RAM is used. This is an intentional timing tradeoff; changes require hardware measurements.

After installation, check ROM startup and the RAM banks. Successful JEDEC verification confirms device programming, but does not validate board timing. See [Troubleshooting](troubleshooting.md).