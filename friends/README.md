# Friends

This directory holds copies of the software which HALFSHIM depends
upon. Please keep in mind that it may not be as uptodate as the
original authors. 

There are a few things I may be able to add.

## Dwight Elvey's Stage-0 BOOTSTRP.ASM

Here is a quick visual check one can use after typing in the 42 bytes
of [BOOTSTRP.OCL] at the monitor.

[BOOTSTRP.OCL]: H89LDR9/BOOTSTRP.OCL

<img src="README.md.d/viewbootstrp.webp" width=80% align="center">

## Running H89TRANS.COM using dosbox

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
  
## Experimental update to h8clxfer.py

Instead of using `H89TRANS.COM`, there is a Python program called
h8clxfer which lets one transfer files easily from the command. Or
rather, there used to be, but it was written for Python 2 which is no
longer supported on modern machines. If you want, you can try an
experimental update to it I've made that runs on modern computers:
[h8clxfer.py][h8clxfer].

[h8clxfer]: friends/h8clxfer.py

