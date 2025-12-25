# absldr: The ½-stage loader for your H89

Run arbitrary programs on the H89 microcomputer without a floppy drive
by loading them over the serial port.

____

# WARNING: THIS IS UNTESTED AND MAY NOT WORK.
____

## Description

After a user has keyed in Dwight Elvey's [BOOTSTRP][H89LDR] at the
Monitor, send first the QUARTERSHIM program from a host computer over
the serial port instead of H89LDR2.ASM. That program will read yet
another program over the serial port, ABSLDR, and execute it, similar to
BOOTSTRP.ASM. The difference is that the next file will be prefixed
with an HDOS .ABS header, which allows the data to be loaded into any
arbitrary address and to be of any length.

[H89LDR]: friends/H89LDR9/

## Quick Usage

Send ABSLDR.BIN instead of H89LDR2.BIN. Then send SOMEFILE.ABS. 

## Usage

After keying in Dwight Elvey's BOOTSTRP, send the ABSLDR binary from
a PC using hackerb9's updated version of [h8clxfer.py][h8clxfer]:

    h8clxfer.py -l -f ABSLDR.BIN

After sending ABSLDR, send an ABS file to start it running:

    h8clxfer.py -l -f GACTAGA.ABS

[h8clxfer]: friends/h8clxfer.py


0. Connect your PC with a straight (not null) serial cable to the port
   labelled **430** on the back of your H89.
1. Turn on your H89 with no disk in the drive. At the **H:** prompt type
   `B`, and hit <kbd>Return</kbd>.
2. Press <kbd>Right-Shift</kbd> + <kbd>Reset</kbd> to stop the boot
   attempt.
3. Type `S 43000` and type in the octal bytes from
   [BOOTSTRP.OCL][BOOTSTRP.OCL] with each one separated by
   <kbd>Space</kbd>. When done, hit <kbd>Return</kbd>.
4. At the **H:** prompt, enter `G 43000` and hit <kbd>Return</kbd>.
5. On your PC, run `h8clxfer.py -l -f ABSLDR.BIN` to send
   ABSLDR.BIN to your H89. Now the shim is waiting for the next
   program to load.
6. On your PC, run `h8clxfer.py -l -f SOMEFILE.ABS` to send
   it to your H89. It will start executing automatically.

[BOOTSTRP.OCL]: friends/H89LDR9/BOOTSTRP.OCL

## About

I wrote this because I recently purchased a Zenith Z-89 and its floppy
drive isn't working yet. 

There is a nifty program by Dwight Elvey called H89LDR which gives the
users a small "Stage 0" boot loader called BOOTSTRP.OCL they can key
into the builtin Monitor program. It is only 43 bytes, but it is just
enough that it can receive the main boot loader over the serial port
and start running it. Normally that program would be H89LDR2 which
lets your PC read from and write to the H89 floppy drives over the
serial port. 

But, if your floppy drive isn't working and you still want to try
running something without keying in every byte, what do you do?

Well, you can try this program. When you send ABSLDR (instead of
H89LDR2) to the Stage 0 bootstrap, it will wait for yet another
program to be sent over the serial port. This time it will expect an
8-byte header before the binary code. That header lets us choose where
the program will be loaded, how many bytes to receive, and jump to
any arbitrary address we want. (Even back to this ½ stage loader, if
more parts are needed to load into memory.)
 
### Header format

ABSLDR expects an 8 byte header which is the same as HDOS's .ABS
format.

	0: FFH	(binary type)
	1: 00H  (ABS object)
	2: ADDR L
	3: ADDR H
	4: LENGTH L
	5: LENGTH H
	6: ENTRYPOINT L
	7: ENTRYPOINT H

ABSLDR places received data starting at ADDR for LENGTH bytes and
then jumps to ENTRYPOINT. To send multiple files, set ENTRYPOINT to
this code's ORG (2329H).

## Creating the bin file

For cross assembly, use asmx -l -e -b2329H -C8080 ABSLDR.ASM

Although it is not necessary for this program, you may wish to try
[Mark Garlanger's hacked version of asmx][mgasmx] which has been
modified for Heathkit computers, such as the ability to directly
create HDOS .ABS files.

[mgasmx]: https://github.com/mgarlanger/asmx

## Caveats

* This is completely untested. If you try this, please leave feedback to
  let me know.

* Running arbitrary .ABS files from HDOS is unlikely to work as they
  will call HDOS routines which aren't loaded into memory.
  Theoretically, one might be able to chain together custom .ABS files
  which load the necessary parts of HDOS into RAM, using the
  ENTRYPOINT address to return to ABSLDR after each one.

* H8 with cassette/serial is not currently supported and is unlikely
  to ever be. The code to handle two different UART chips is uglier
  than I'd like for a tiny program like this. It seems better to
  create a separate program. Additionally, in the future, the plan is
  to have ABSLDR show text on the H89 screen when it is running,
  which would rule out the H8-5 serial card which uses the same I/O
  port as the terminal part of the H89.

## Notes
1. Stack pointer is initialized to end of memory by MTR at power-on.
2. CPU speed should not be an issue.
   1. At 9600 baud, a byte arrives approximately every millisecond.
   2. Execution path from GETCH to GETCH is 54 T-states ≈ 0.027 ms.
3. The DS assembler macro is used to bulk out this program to
   DBEND so that BOOTSTRP.ASM does need not be changed. This
   program will be loaded into 2329H-265BH, same as H89LDR2.


## TODO

1. Test it on actual hardware.

2. Output text to the H89 / H19 screen.

3. Try running non-trivial HDOS .ABS programs by preloading parts of
   HDOS into RAM. 

4. This version does not handle the H8 w/ cassette/serial board.
   Should a different version be made? If it had to, it could check if
   COMTYPE at byte 2313H from BOOTSTRP/BOTSTRP8 is FAH. If so, then
   use H8-5 code instead of the H8-4/H89 code. (See H89LDR2.ASM).

