#!/usr/bin/python3
import serial
import serial.tools.list_ports
import sys
import os
import time

# --- Platform-specific Key Handling ---
if os.name == 'nt':
    import msvcrt
    def get_key(): return msvcrt.getch().decode('ascii', errors='ignore') if msvcrt.kbhit() else None
else:
    import termios, tty, select
    def get_key():
        # Source - Unix get key from Python 3 documentation
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

class H89Trans:
    def __init__(self):
        self.ser = None
        self.port = None
        self.baud = 9600
        self.vol = 0
        self.interleave_factor = 0x31  # ASCII '1'
        self.override = False
        self.track_size = 2560


    def initialize_port(self, port, baud):
        try:
            ser = serial.Serial(port, baud, timeout=1)
            print(f"Connected to {port} at {baud} baud.")
            return ser
        except serial.SerialException as e:
            print(f"\n--- ERROR: Could not open port {port} ---")
            print(f"Details: {e}")
            exit(1)

    def select_port(self):
        """Finds and opens a serial port."""
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

        self.ser = self.initialize_port(self.port, self.baud)

    def select_port_menu(self, ports):
        if not ports:
            print("No serial ports detected! Check your USB cables.")
            return None

        while True:
            print("\nAvailable Serial Ports:")
            for i, p in enumerate(ports):
                print(f"{i+1}) {p.name} - {p.description}")

            print("Select a port number: ", end='', flush=True)
            choice = get_key();
            print(choice)
            try:
                idx = int(choice) - 1
                return ports[idx].device
            except (ValueError, IndexError):
                print("Invalid selection.")

    def wait_char(self, target):
        """WaitChar. Blocks until target received."""
        target = ord(target.upper())
        while True:
            try:
                raw = self.ser.read(1)
                if not raw: continue

                # Save the raw character to a class variable (=: CharOfWait)
                self.char_of_wait = raw.decode('ascii', errors='ignore')

                # Check case-insensitively ($DF AND)
                if self.char_of_wait.upper() == target:
                    break

            except serial.SerialException:
                print("\nConnection lost during wait_char."); return


    def check_read_error(self):
        """CkRdErr, checks for lowercase instead of uppercase R."""
        if self.char_of_wait == 'r':
            print("\nRead error was detected on this track!")

    def y_n_prompt(self):
        """Y/N?"""
        while True:
            k = get_key()
            if k:
                k = k.lower()
                if k == 'y': return True
                if k == 'n': return False
                print("\n Y or N pls? ", end='', flush=True)

    def set_interleave(self):
        """SetIntrLv."""
        while True:
            print("\n"
                  "Set Interleave 1:1 enter 1\n"
                  "               1:2 enter 2\n"
                  "               1:3 enter 3", flush=True)
            k = get_key()
            print(k)
            if k in ['1', '2', '3']:
                self.interleave_factor = int(k)
                print(f"Interleave set to 1:{k}")
                break

    def send_interleave(self):
        """Replicates 'SendIntrLv'. Transmits command 'I' then (factor - 1)."""
        print(f"Sending Interleave 1:{self.interleave_factor} to H89...")
        self.ser.write(b'I') # Send command
        # Matches Forth: ascii 1 - SendChar
        val_to_send = self.interleave_factor - 1
        self.ser.write(bytes([val_to_send]))
        self.wait_char('I')
        print("Interleave accepted by H89.")

    def set_baud_rate(self):
        """SetNewBaud."""
        print("\nSelect Baud Rate:")
        rates = {'1':1200, '2':2400, '3':4800, '4':9600, '5':19200, '6':38400, '7':57600, '8':115200}
        for k, v in rates.items(): print(f"{k}) {v}")
        c = input("Choice: ")
        if c in rates:
            self.baud = rates[c]
            if self.ser:
                self.ser.baudrate = self.baud
                print(f"Baud rate updated to {self.baud}")
        else:
            print( f'{c} is not a valid number!' )

    def write_disk(self):
        """WrImage: Send a disk image to the H89."""
        fname = input("Enter source image filename: ")
        if not os.path.exists(fname): return
        
        self.send_interleave() 
        
        with open(fname, "rb") as f:
            # 1. SEND INITIAL 'W' (Writing image to disk)
            self.ser.write(b'W')

            for track in range(40):
                print(f"\rWriting Track {track}... ")
                data = f.read(self.track_size)

                # 2. SEND PER-TRACK 'W' (Track Start)
                self.ser.write(b'W')

                # 3. SEND TRACK DATA
                for byte in data: self.ser.write(bytes([byte]))

                # 4. WAIT FOR 'W' (Handshake/Confirmation)
                self.wait_char('W')

            print("\nDisk Write Complete.")

    def write_loader(self, filename="H89LDR2.BIN"):
        try:
            with open(filename, "rb") as f:
                data = f.read()
                file_size=len(data)
                LDR_SIZE = (0x265B - 0x2329)  # 818 bytes
                if file_size != LDR_SIZE:
                    print(f"Error: {filename} is {file_size} bytes, expected {LDR_SIZE}.")
                    return
                else:
                    print(f"Sending {filename} ({file_size} bytes)...")

                # Send bytes in reverse-order to match Forth '1- dup c@'
                for byte in reversed(data):
                    # Check if H89 sent anything back
                    if self.ser.in_waiting > 0:
                        if self.ser.read(1) == b'?':
                            print("\nAlready loaded?")
                            return 
                    # Send the next byte of the loader
                    self.ser.write(bytes([byte]))

                # 2. 40 Null bytes padding erases stage 0 loader
                for _ in range(40): self.ser.write(b'\x00')

                # 3. Make sure the next stage loader is alive
                self.ser.write(b'A')
                self.wait_char(chr(ord('?') ^ 0x20))
                print("H89 Loader active and responding.")
        except OSError as e:
            print(f"Can't read Loader File '{filename}'?")
            print(e)
            return

    def read_disk(self):
        """RdImage with track progress and byte-by-byte reads."""
        fname = input("Enter filename to save image into: ")
        if not self.override:
            self.ser.write(b'C')  # DiskVol#
            ch = None
            while not ch:
                ch = self.ser.read(1)
            self.vol = ord(ch)
            self.wait_char('C')
            print(f"Volume on disk identified as: {self.vol}")

        try:
            with open(fname, "wb") as f:
                self.ser.write(b'R')
                for track in range(40):
                    print(f"\rTrack {track} Receiving... ", end='', flush=True)
                    self.ser.write(b'R')
                    buffer = bytearray()
                    for _ in range(self.track_size):
                        buffer.extend(self.ser.read(1))
                    self.wait_char('R')
                    self.check_read_error()
                    f.write(buffer)
                print(f"\nRead Complete. Disk image saved in {fname}.")
        except OSError as e:
            print(f"Can't read '{filename}'?")
            print(e)
            return

    def terminal(self):
        """Terminal mode 'T' with status dump hook."""
        print("\nTerminal Mode. ESC to exit. Ctrl+R for Status.")
        while True:
            k = get_key()
            if k == '\x1b': break # ESC
            if k == '\x12': # Ctrl+R (PP replacement)
                print(f"\n[Status] Port: {self.port} | Baud: {self.baud} | Vol: {self.vol}")
            elif k: self.ser.write(k.encode('ascii'))
            
            if self.ser.in_waiting:
                sys.stdout.write(self.ser.read(1).decode('ascii', errors='replace'))
                sys.stdout.flush()

def main():
    try:
        h = H89Trans()
        h.select_port()
        while True:
            print(f"\n--- H89 Utility (2025) --- Port: {h.port}")
            print(f"Baud: {h.baud} | Vol: {h.vol} | Override: {h.override}")
            print("L) Load H89LDR2.BIN (RAM)     V) Set Volume Number")
            print("R) Read H89 Disk to Image     I) Set Interleave Factor")
            print("W) Write PC Image to H89 Disk    O) Volume Override (Y/N)")
            print("S) Save Loader to H89 Boot    B) Change Baud Rate")
            print("T) Terminal Mode              Q) Quit Utility")

            print("Command?", end='', flush=True)
            choice = get_key().upper()
            print(choice)
            try:
                if choice == 'L': h.write_loader()
                elif choice == 'R': h.read_disk()
                elif choice == 'V': h.vol = int(input("Volume: "))
                elif choice == 'I': h.set_interleave()
                elif choice == 'O': 
                    print("\nUse image Vol#? (Y/N)")
                    h.override = not h.y_n_prompt()
                elif choice == 'S': 
                    h.ser.write(b'S'); h.wait_char('S')
                    print("Loader saved to remote disk.")
                elif choice == 'B': h.set_baud_rate()
                elif choice == 'T': h.terminal()
                elif choice == 'Q' or choice == 'X': break
            except serial.SerialException as e:
                print("\n--- ERROR: Port may have been disconnected. ---")
                print(f"Details: {e}")
                h.select_port()
        
    except KeyboardInterrupt as e:
        print("\nExiting")
        print(f"Details: {e}")
        exit(0)

if __name__ == "__main__":
    main()
