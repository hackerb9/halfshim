# Friends

This directory holds copies of related software. 

* [H89LDR](H89LDR9)
* [h8clxfer][h8clxfer]
* [HDOS Shim][hdosshim]

## Dwight Elvey's H89LDR 

This is a copy from Version 9 (2025). It may not be as up-to-date as
from the original authors.

### Dwight Elvey's Stage-0 BOOTSTRP.ASM

Here is a quick visual check one can use after typing in the 42 bytes
of [BOOTSTRP.OCL] at the monitor.

[BOOTSTRP.OCL]: H89LDR9/BOOTSTRP.OCL

<img src="README.md.d/viewbootstrp.webp" width=80% align="center">

### Running H89TRANS.COM using dosbox

Linux tip: If you run H89TRANS.COM using dosbox, you'll need to
configure it to use your PC's actual serial port. Edit the file
~/.dosbox/dosbox-0.74-3.conf and change the line which says:

	serial1=dummy

to

	serial1=directserial realport:ttyUSB0

* Note 1: Enumerating your serial ports. `ttyUSB0` is typical for USB
  serial devices. For a buitin serial port on a computer, it will
  often be `ttyS0`. To see the names of the serial ports installed on
  your computer, type this:

        ls -l /dev/serial/by-id

* Note 2: Requiring users to have different configuration files for
  different version of dosbox is extraordinarily silly. Hopefully that
  is just a passing phase. 
  
## HDOS Shim

[HDOS Shim][hdosshim] is an attempt to make .abs files which setup RAM
as if HDOS was running and then return to ABSLDR.

## Experimental update to h8clxfer.py

Instead of using `H89TRANS.COM`, there is a Python program called
h8clxfer which lets one transfer files easily from the command. Or
rather, there used to be, but it was written for Python 2 which is no
longer supported on modern machines. If you want, you can try an
experimental update to Python 3 I've made:
[h8clxfer.py][h8clxfer].

Caveat: Be aware that h8clxfer.py seems to not use exactly the same
protocol as Dwight Elvey's `H89TRANS.COM`. 

[h8clxfer]: friends/h8clxfer.py

