#!/usr/bin/python3

# Based on Dwight Elvey's H89TRANS.SEQ

# v 2.0 Adding support for communicating with QUARTERSHIM and ABSLDR. 
# v 1.0 This is a one-to-one port from Forth to Python by hackerb9.

# It should work almost identically to H89TRANS.COM as it is nearly
# identical at the function call level. The main difference is not
# having to twiddle the bits of the PC's UART directly and instead
# using the Python serial package.

# Unlike the original code, this can run on any modern computer. It
# also has some minor niceties, such as automatically detecting your
# serial ports, not bombing out on unexpected input, showing the list
# of files when selecting an image (hit Enter) and allowing one to
# choose directories.
#
# There are also some basic safety checks. The most obtrusive of those
# is that one can no longer accidentally overwrite existing disk images.
# Whether you're opening a file for reading or writing is determined
# by if the file exists and has data (the former) or not (the later).

# Translating most of the original code was straightforward once I
# learned rudimentary Forth. The parts I have questions about have
# been marked with XXX below.

# Forth words not translated to Python as there was no need: PP,
# SetCom, Char?, RdySend, SendChar, SendChars, RecChar, Echo?,
# SetDelay, Baud!, CharBack, PutChr, GetImageHandle, WrBuf, ChkNum,
# ChkSize (?needed?), and ClearChar.

# Of course, any other differences are likely bugs on my part and I
# would appreciate if you would file an issue or a pull request.

# --b9 December 2025

# License is the same as whatever Dwight originally used,
# falling back to the MIT License if necessary.

import serial
import serial.tools.list_ports
import sys
import os
import time

# Test without any serial ports
DEBUG = True


# --- Platform-specific Key Handling ---
if os.name == 'nt':
    import msvcrt
    def _get_key(): return msvcrt.getch().decode('ascii', errors='ignore') if msvcrt.kbhit() else None
else:
    import termios, tty, select
    def _get_key():
        # Source - Unix get_key from Python 3 FAQ.
        import termios, fcntl, sys, os
        fd = sys.stdin.fileno()

        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)

        oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)

        try:
            while 1:
                try:
                    c = sys.stdin.read(1)
                    if c: return c
                except IOError: pass
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
            fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)

    def get_key(prompt=''):
        print(prompt, end='', flush=True)
        c = _get_key()
        print( c  if c.isprintable()  else f'[{ord(c):02X}H]' )
        return c

    def errout():
        """ErrOut: Quits this program with an error."""
        exit(1)


class H89Trans:
    BBEGIN = 0x2300            # BOOTSTRP.ASM's ORG
    BEND = 0x2329              # BOOTSTRP.ASM's last byte (next loader's ORG)
    LBEGIN = 0x2329            # H89LDR2.ASM's ORG (yes, this overwrites BEND)
    LEND = 0x265B              # H89LDR2.ASM's DBEND
    LDR_SIZE = LEND-LBEGIN     # H89LDR2.BIN's size (818 bytes)

    FBEGIN = 0x1400             # Floppy RAM start (ABSLDR's ORG)
    FEND = 0x1800 - 1           # Floppy RAM last byte
    FSIZE = FEND-FBEGIN+1       # Floppy RAM length (1K)

    def __init__(self):
        self.ser = None            	# The serial.Serial object.
        self.port = None        	# Automatically detected
        self.default_baud = 9600        # 9600 is good for H89's H8-4
        self.interleave_factor = 1 	# Write 1:1 disk interleave by default
        self.num_tracks = 40            # 40 track disks
        self.track_size = 0x0A00 	# 2560 bytes per track
        self.vol = 0                    # Disk volume number 0-255
        self.override = False    	# Should we override the Vol read?
        self.char_of_wait = None        # Character read during wait_char
        self.read_errors = 0            # Number of read errors encountered
        self.fp = None                  # The image file on the PC
        self.fp_dir = None              # Guard against clobbering files.
        				# (fp_dir ∈ {'to h89', 'from h89'}) 

    def select_port(self):
        """SlctCom: Finds and opens a serial port."""
        ports = serial.tools.list_ports.comports()
        if not ports:
            print("No serial ports detected! Check your USB cables.")
            exit(1)

        # For some reason Python's serial sometimes shows bogus serial ports.
        # This hides them, but may also hide genuine builtin serial cards.
        goodports = [ x for x in ports if x.hwid != 'n/a' ]
        if goodports:
            ports = goodports

        if len(ports) == 1:
            self.port = ports[0].device
        else:
            self.port = self.select_port_menu(sorted(ports))

        self.ser = self.initialize_port(self.port, self.default_baud)

    def select_port_menu(self, ports):
        """GetCom, SetCom: Select a serial port"""
        if not ports:
            print("No serial ports detected! Check your USB cables.")
            return None

        while True:
            print("\nAvailable Serial Ports:")
            for i, p in enumerate(ports):
                print(f"{i+1}) {p.name} - {p.description}")


            choice = get_key("Select a serial port? ")
            try:
                idx = int(choice) - 1
                return ports[idx].device
            except (ValueError, IndexError):
                print( 'That is not a valid number!' )

    def initialize_port(self, port, baud):
        """InitPort: Initialize the port to 9600 baud"""
        try:
            ser = serial.Serial(port, baud, timeout=1, stopbits=2)
            print(f"Connected to {port} at {baud} baud.")
            return ser
        except serial.SerialException as e:
            print(f"\n--- ERROR: Could not open port {port} ---")
            print(f"Details: {e}")
            if not DEBUG:
                exit(1)
            else:
                return serial.Serial()

    def pp(self):
        """PP: Test word used to check status of ports"""
        if self.ser:
            from pprint import pprint
            pprint(self.ser.get_settings())

    def wait_char(self, target):
        """WaitChar. Blocks until target char received from H89."""
        if type(target) is str:
            target = bytes(target, encoding='UTF-8')
        target = target.upper()
        while True:
            try:
                raw = self.ser.read(1)
                if not raw: continue
                # Save upper/lower case for later...
                self.char_of_wait = raw
                # ... but inspect as upper case.
                if raw.upper() == target:
                    break
                else:
                    print(f"wait_char: Waiting for {prtchr(target)}, "
                          f"got {prtchr(raw)}", flush=True)

            except serial.SerialException:
                print("\nConnection lost during wait_char."); return

    def send_volume(self, vol=None):
        """SetVol: Tell H89 which disk volume to use."""
        if not vol: vol=self.vol
        if not (0 <= vol <= 255):
            # XXX Will this ever trigger? The default volume number is 0.
            print("No volume number set?")
            return
        self.ser.write(b'V')
        self.ser.write(bytes([vol]))
        self.wait_char('V')
        print(f"H89 Volume set to {vol}")

    def y_n_prompt(self):
        """Y/N?"""
        while True:
            k = get_key().upper()
            if k == 'Y': return True
            if k == 'N': return False
            print("Y or N pls?", end='', flush=True)

    def file_prompt(self, prompt):
        while True:
            try:
                print(prompt, end="")
                filename = input().strip()

                if not filename:
                    print('Press Ctrl+C to cancel')
                    print('Current directory: [' + os.path.realpath('.') + ']')
                    print('Directory listing:', ', '.join(os.listdir('.')))
                    continue

                # Tolerate habitual DOSisms?
#                if filename.startswith('chdir '): filename = filename[6:]
#                if filename.startswith('cd '):    filename = filename[3:]

                # Vaguely case-insignificant (if filenames are uppercase). 
                if ( not os.path.exists(filename) and os.path.exists(filename.upper()) ):
                    filename=filename.upper()

                if os.path.isdir(filename):
                    os.chdir(filename)
                    print('[' + os.path.realpath('.') + ']')
                    print(', '.join(os.listdir('.')))
                else:
                    return filename
            except KeyboardInterrupt as e:
                # Allow Control-C to cancel opening a file
                return None

    def open_image_file(self):
        """OpenImageFile: Prompt for a filename to open/create."""
        if self.fp: self.fp=None

        filename = self.file_prompt("\nimage file? ")
        if not filename:
            print('Cancelled')
            return False

        if os.path.exists(filename) and os.path.getsize(filename):
            b = os.path.getsize(filename)
            print(f"Reading existing file of {b:,} bytes")
            try:
                self.fp = open(filename, 'rb')
                self.fp_dir = 'to h89'
            except IOError:
                print("Couldn't open file?")
                self.fp = None
        else:
            print("File Doesn't Exist. I'll create")
            try:
                self.fp = open(filename, 'wb')
                self.fp_dir = 'from h89'
            except IOError:
                print("Couldn't create file?")
                self.fp = None
                return

    def get_disk_volume(self):
        """
        DiskVol#: Queries the H89 for the disk's current volume number.
        """
        # XXX The original Forth code does '2 0 do', performing the check
        # XXX and printing it twice. Why? Possibly because we don't know
        # XXX the state on the H89? Note that the original code also has
        # XXX some commented out flow control statements, indicating that
        # XXX perhaps this bit of code may not be completely up to snuff.
        # XXX Why would checking twice help? Does the volume reported vary?
        for _ in range(2):
            self.ser.write(b'C')
            raw_vol = self.ser.read(1)
            if raw_vol:
                self.vol = ord(raw_vol)
                print(f"Volume detected: {self.vol}")
            else:
                print("Error: No volume response from H89.")
                return False
            self.wait_char('C')
        return True

    def is_h89ldr2_alive(self):
        """Is H89LDR2 loaded and responding?"""
        self.ser.write(b'A')
        ch = self.ser.read(1)   # See initialize_port for timeout.
        if not ch:
            print("\n    Error: H89 is not responding.")
            print("    Please Load H89LDR2 and check cables.")
            return False
        else:
            return True

    def read_track_volume_problem(self):
        """RdDiskVol: Reads and checks the actual volume number on tracks
        If it doesn't match then problem, return true."""
        self.ser.write(b'T')
        track_vol_raw = self.ser.read(1)
        if not track_vol_raw:
            print('Error: No Track Volume response')
            return True # Treat as error if no response
        track_vol = ord(track_vol_raw)
        self.wait_char('T')

        if track_vol != self.vol:
            print(f"\nVol# {self.vol} not = tracks Vol# = {track_vol}")
            return True # Error flag

        return False # Success

    def check_read_error(self):
        """CkRdErr, checks for lowercase instead of uppercase R."""
        if self.char_of_wait == 'r':
            print("Read error was detected on this track!")
        self.read_errors+=1

    def read_disk(self):
        """RDImage: Read disk image from H89 to PC."""
        if not self.fp: 
            print('\n  Please Open an image file to receive into first.')
            return

        if self.fp_dir == 'to h89':
            print(f'\n  The file "{self.fp.name}" is opened for reading.')
            print(   '  Please Open an new image file to receive into.')
            return

        if not self.is_h89ldr2_alive():
            return

        if not self.override:
            if not self.get_disk_volume():
                return
            print(f"Volume on disk identified as: {self.vol}")
            # XXX: Should the Track Volume be checked on every track?
            if self.read_track_volume_problem():
                # XXX: Should we attempt to recover or offer to set the vol?
                return

        print(f'Receiving disk into {self.fp.name} from the H89')

        try:
            self.fp.seek(0)
            self.read_errors=0
            self.ser.write(b'R')

            for track in range(self.num_tracks):
                print(f"\rReceiving Track {track}... ", end='', flush=True)
                self.ser.write(b'R')
                buffer = bytearray()
                for _ in range(self.track_size):
                    buffer.extend(self.ser.read(1))
                self.wait_char('R')
                self.check_read_error()
                self.fp.write(buffer) 		# WrBuf

            self.fp.close()
            self.fp = None
            print(f"\nRead Complete. Disk image saved in {fname}.")
            if self.read_errors:
                print(f"\n  WARNING: {self.read_errors} "
                      f"Read Error{s(self.read_errors)}.\n")
        except OSError as e:
            print(f"Error: Can't write '{filename}'?")
            print(e)
            return

    def get_image_volume(self):
        """FileVol#: Read the Vol# out of an image file"""
        if not self.fp:
            print ("Error in get_image_volume: No File Open?")
            return self.vol
        try:
            self.fp.seek(0x900)     # Offset 2304
            raw = self.fp.read(1)
            self.fp.seek(0) 
            if raw:
                self.vol = ord(raw)
                print(f"Image file's volume#: {self.vol}")
            return self.vol
        except OSError as e:
            print(f"Error: Can't read '{self.fp.name}'?")
            print(e)
            return self.vol

    def read_track_from_image(self):
        """RdBuf: Read one track of data from the file buffer"""
        track = self.fp.read(self.track_size)
        if len(track) != self.track_size:
            print("Short read: {len(track)}/{self.track_size}. Unable to read file?")
            errout()
        else:
            return track

    def volume_override(self):
        """VolOverRide: enable/disable overriding the disk volume number."""

        print( "\nUse image Vol#? (Y/N)" if self.override
              else "\nOver ride image Vol #? (Y/N)", end=" ")

        # If user says 'Y', we flip the current state
        if self.y_n_prompt():
            self.override = not self.override

    def get_volume(self):
        # GetVol#: Prompt for Volume #, if overriding
        self.volume_override()
        if self.override:
            try:
                val = input(f"Enter Vol# [{self.vol}]: ")
                if val: self.vol = int(val) & 0xFF  # Ensure 8-bit
            except ValueError: print("   Invalid - Vol# unchanged.")

    def set_interleave(self):
        """SetIntrLv: Ask user what floppy disk interleave they would like"""
        while True:
            k = get_key("\nSet interleave  = 1:")
            if k in ['1', '2', '3']:
                self.interleave_factor = int(k)
                print(f"Interleave set to 1:{k}")
                break
            else:
                print("\n"
                      "Set Interleave 1:1 enter 1\n"
                      "               1:2 enter 2\n"
                      "               1:3 enter 3", flush=True)


    def send_interleave(self):
        """Replicates 'SendIntrLv'. Transmits command 'I' then (factor - 1)."""
        print(f"Sending Interleave 1:{self.interleave_factor} to H89...")
        self.ser.write(b'I')
        self.ser.write(bytes([self.interleave_factor - 1]))
        self.wait_char('I')
        print("Interleave accepted by H89.")

    def save_loader_to_disk(self):
        if not self.is_h89ldr2_alive():
            return
        self.send_volume(0)     # Temporarily set the volume to 0 on the H89
        self.ser.write(b'S')    # H89LDR2 knows what to do when it receives 'S'
        self.wait_char('S')     # Wait for the H89 to finish.
        print("H89LDR2 saved to bootable disk on H89.")

    def write_disk(self):
        """WrImage: Send a disk image to the H89."""
        if not self.fp: 
            print('\n  Please Open an image to send first.')
            return

        if self.fp_dir == 'from h89':
            print(f'\n  The file "{self.fp.name}" is opened for writing.')
            print('  Please Open an existing image file to send first.')
            return

# XXX why is this failing?
        #if not self.is_h89ldr2_alive():
        #    return

        print(f'Writing {self.fp.name} to the H89 floppy drive')

        try:
            if self.override:
                self.send_volume(self.vol)
            else:
                self.send_volume(self.get_image_volume())
            self.fp.seek(0)
            self.send_interleave() 
            self.ser.write(b'W')

            for track in range(self.num_tracks):
                print(f"\rWriting Track {track}... ", end='', flush=True)
                data = self.read_track_from_image()
                self.ser.write(b'W')
                self.ser.write(bytes(data))
                self.wait_char('W')

            print("\nDisk Write Complete.")

        except OSError as e:
            print(f"Error: Can't read '{filename}'?")
            print(e)
            return

    def write_loader(self, filename="H89LDR2.BIN", ldr_size = None):
        """WrLdr: Load the next stage loader, H89LDR2, on the H89.
        Presumes stage zero (BOOTSTRP.OCL) was already entered by hand."""

        if not ldr_size:
            ldr_size = self.LDR_SIZE 		# 818 bytes
        try:
            with open(filename, "rb") as f:
                data = f.read()
                file_size=len(data)
                if file_size != ldr_size:
                    print(f"Error: {filename} is {file_size} bytes, expected {ldr_size}.")
                    return
                else:
                    print(f"Sending {filename} ({file_size} bytes)...")

                if self.ser.in_waiting > 0:
                    print('Flushing serial input: ', end='')
                    while self.ser.in_waiting > 0:
                        print(prtchr(self.ser.read(1)), end='')
                    print()

                # Send bytes in reverse-order to match Forth '1- dup c@'
                for byte in reversed(data):
                    # Check if H89 sent anything back
                    if self.ser.in_waiting > 0:
                        if self.ser.read(1) == b'?':
                            print("\nAlready loaded?")
                            return 
                    # Send the next byte of the loader
                    self.ser.write(bytes([byte]))

                # At this point, the next loader should have started
                # on the H89 as the final byte sent overwrites the
                # last byte of BOOTSTRP.
                self.ser.write(b'\x00' * 40)

                # Make sure the next stage loader is alive
                self.ser.write(b'A')
                # XXX Why did Forth xor '?' with 0x20 instead of straight?
#                self.wait_char(chr(ord('?') ^ 0x20))
                self.wait_char('?')
                print("H89 Loader active and ready.")
        except OSError as e:
            print(f"Can't read Loader File '{filename}'?")
            print(e)
            return

    def write_absloader(self, filename="ABSLDR.BIN"):
        """Experimental! If QUARTERSHIM is loaded, try sending ABSLDR into the H89's Floppy RAM"""
        try:
            actual_size = os.path.getsize(filename)
            if actual_size != 1024:
                print(f'ERROR: Size of "{filename}" was {actual_size} bytes. Should be 1024.', file=sys.stderr)
                return False
            # Make sure QUARTERSHIM is running
            # At this point, the next loader should have started
            # on the H89 as the final byte sent overwrites the
            # last byte of BOOTSTRP.
            self.ser.write(b'F')
            print('Checking if QUARTERSHIM is running on H89... ', end='', flush=True)
            # This rules out H89LDR2 which will respond '?'
            self.wait_char('F')
            print('All good.')

            print(f"\rSending {filename} to H89... ", end='', flush=True)
            with open(filename, 'rb') as fp:
                data=fp.read()
                self.ser.write(bytes(reversed(data)))
                print(f"{len(data)} bytes sent")
                print('Awaiting confirmation from H89... ', end='', flush=True)
                self.wait_char('F') 
                print('Confirmed.')

        except OSError as e:
            print(f"Problem reading '{filename}'?")
            print(e)
            return

    def send_abs(self):
        """Experimental! If ABSLDR is loaded, try sending an ABS file to the H89"""
        if not self.fp: 
            print('\n  Please first Open an ABS file to send.')
            return

        if self.fp_dir == 'from h89':
            print(f'\n  The file "{self.fp.name}" is opened for writing.')
            print('  Please Open an existing ABS file to send first.')
            return

        print(f'File size: {os.path.getsize(self.fp.name)}')
        try:
            self.fp.seek(0)
            s = self.fp.read(8)
            import struct
            (magic, addr, length, entry) = struct.unpack('<HHHH', s)
            print(f'Magic: {magic:04X}H, '
                  f'Load Addr: {addr:04X}H, '
                  f'Length: {length:04X}H, '
                  f'Entry: {entry:04X}') 
            endaddr=addr+length
            if endaddr > 0xFFFF:
                print('\n    WARNING: This writes beyond 64K of RAM!\n')
            if addr <= self.FEND and endaddr >= self.FBEGIN:
                print(f'\n    WARNING: This overwrites ABSLDR ({self.FBEGIN:04X}H) and will fail!\n')
            if addr <= self.BEND and endaddr >= self.BBEGIN:
                print(f'    NOTE: This overwrites BOOTSTRP ({self.BBEGIN:04x}).')
            if addr <= self.LEND and endaddr >= self.LBEGIN:
                print(f'    NOTE: This overwrites QUARTERSHIM ({self.BEND:04x}).')
            if entry == self.FBEGIN:
                print('    NOTE: This multipart file runs ABSLDR again.')
            else:
                if entry < addr or endaddr < entry:
                    print('\n    WARNING: Transfers control an entry point outside the program.\n')
            if magic != 0x00FF and magic != 0x01FF:
                print('\n    ERROR: {self.fp.name} is not an ABS file!')
                print(  '           Magic should be 00FFH, not {magic:04X}H\n')
                return 1

            # Make sure ABSLDR is running
            print('Checking if ABSLDR is running on H89... ',
                  end='', flush=True)
            self.ser.write(b'B')
            # This rules out H89LDR2 which will respond '?'
            self.wait_char('B')
            print('All good.')

            self.fp.seek(0)
            print(f"\rSending {self.fp.name} to H89... ", end='', flush=True)
            data = self.fp.read()

            self.ser.write(bytes(data))
            print(f"{len(data)} bytes sent")
            print('Awaiting confirmation from H89... ', end='', flush=True)
            self.wait_char('B')
            print('Confirmed.')

        except OSError as e:
            print(f"Problem reading '{self.fp.name}'?")
            print(e)
            return

    def set_baud_rate(self):
        """SetNewBaud: Prompt user to select a new baudrate"""
        rates = {'4':9600, '3':4800, '2':2400, '1':1200, }
        #        '5':19200, '6':38400, '7':57600, '8':115200}
        print("\nSelect Baud ", end='')
        for k, v in rates.items(): print(f" {k}={v} ", end='')
        c = get_key('? ')
        if c in rates:
            self.ser.baudrate = rates[c]
            print(f"Baud rate updated to {self.ser.baudrate}")
        else:
            print( f'{c if c.isprintable() else "that"}',
                   'is not a valid number!' )
            print( f'Baud rate remains at {self.ser.baudrate}' )

    def display_menu(self):
        """Cmnd?: Show options and get a key"""
        print("")
        print("V set volume#  [now:",
              f"Override = {self.vol}]" if self.override else "From Image]")
        print("O open/create image file  [now: "
              f"{self.fp.name if self.fp else 'None'}]")
        if self.fp and self.fp_dir == 'to h89':
            print("W write image to H89")
        if self.fp and self.fp_dir == 'from h89':
            print("R read image from H89")
        print("L Send H89LDR2.BIN to H89")
        print("S Save loader on H89")
        print("I Set interleave  [= 1:"
              f"{self.interleave_factor}"  "]")
        print("B Set Baud rate  [= "
              f"{self.ser.baudrate}" "] (for use with H8-5)")
        print("X exit to DOS")

        return get_key("\nCommand? ").upper() 

    def command_execute(self, choice):
        """CommandEx: Execute the key pressed from the menu."""
        if   choice == 'V': self.get_volume()
        elif choice == 'O': self.open_image_file()
        elif choice == 'W': self.write_disk()
        elif choice == 'R': self.read_disk()
        elif choice == 'L': self.write_loader()
        elif choice == 'S': self.save_loader_to_disk()
        elif choice == 'I': self.set_interleave()
        elif choice == 'B': self.set_baud_rate()

        # XXX To do: show these in the menu
        elif choice == 'P': self.pp()
        elif choice == 'Q': self.write_loader('QUARTERSHIM.BIN')
        elif choice == 'F': self.write_absloader('ABSLDR.BIN')
        elif choice == 'A': self.send_abs()

        elif choice == 'X' or choice == '\x1B': 
            print("Exiting to DOS...")
            exit(0)

def split_octal(i):
    """.SO: Display a 16-bit value in "split octal" notation.
    The .SO word was present but unused in the original Forth code.  

    "Split Octal" is shown as two bytes each represented by an octal
    number from 000 to 377, often just smushed together.
    Mathematically, that's wrong as the number after 000377 should be
    000400 (in normal octal), but in split octal it is 001000

    I'm using the convention of adding a space between the two bytes
    to help disambiguate, but honestly there's a good reason this
    routine wasn't used: Hexadecimal is simply better for 8-bit bytes.
    """
    if (i<0 or i>65535):
        raise OverflowError('Split octal can only represent numbers from 0 to 65535') 
    print( f'{i//256:03o} {i%256:03o}' )

def prtchr(c):
    '''Given a character k, return a printable string for it, if
    possible, including its hex value. A -> "A" (41H)
    '''
    if c:
        o = f'{ord(c):02X}H'
        if type(c) is bytes:  c = c.decode(errors='ignore')
        if c.isprintable():  
            return f"'{c}' ({o})"
        else:
            return f"({o})"
    else:
        return ""

def s(i:int) -> str:
    '''Plural(s)'''
    return "" if i == 1 else "s"

def main():

    """Command: Configure port, show menu, execute commands""" 
    h = None
    try:
        assert ('foo')
        h = H89Trans()
        h.select_port()
        while True:
            try:
                choice = h.display_menu()
                h.command_execute( choice )

            except serial.SerialException as e:
                print("\n--- ERROR: Port may have been disconnected. ---")
                print(f"Details: {e}")
                h.select_port()
        
    except KeyboardInterrupt as e:
        print('\nExiting')
    finally:
        if h and h.fp:
            h.fp.close()
            if os.path.getsize(h.fp.name) == 0:
                print(f'Removing empty file "{h.fp.name}"')
                os.unlink(h.fp.name)
        exit(0)

if __name__ == "__main__":
    main()
