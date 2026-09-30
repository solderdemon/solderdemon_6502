# rosco_6502 PLDs

[Building and programming PLDs](../../docs/pld-firmware.md) provides the full instructions.

r5 replaces both GALs and the 555 reset timer with one ATF1502AS, programmed in the board over JTAG (J8):

| Position | Source | JEDEC | Build |
| --- | --- | --- | --- |
| IC2 (r5) | [ic2_glue.pld](cpld/ic2_glue.pld) | [ic2_glue.jed](cpld/ic2_glue.jed) | [build.sh](cpld/build.sh), fitter report [ic2_glue.fit](cpld/ic2_glue.fit) |

r4 GALs:

| Position | Source | JEDEC | Programming script |
| --- | --- | --- | --- |
| IC2 | [ic2_address_decoder.pld](address_decoder/ic2_address_decoder.pld) | [ic2_address_decoder.jed](address_decoder/ic2_address_decoder.jed) | [burn.sh](address_decoder/burn.sh) |
| IC5 | [ic5_glue_logic.pld](glue/ic5_glue_logic.pld) | [ic5_glue_logic.jed](glue/ic5_glue_logic.jed) | [burn.sh](glue/burn.sh) |

The scripts program existing JEDEC files into ATF22V10C(UES) devices. Run each script from its own directory. After changing equations, rebuild the JEDEC files as described in the guide before programming.

[Documentation index](../../docs/README.md)