#! /usr/bin/python3
#
# h8clxfer.py
# (c) 2011,2012,2025 George Farris <farrisg@gmsys.com>  
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

#=============================================================================================
#
# Command line version.
#
# Version 0.1 - Feb 21, 2011 -Read and write CP/M disks
#         0.2 - Feb 22, 2011 -Added ability to read and write HDOS disks
#         0.3 - Feb 23, 2011 -Fixed set volume bug
#         0.4 - Feb 24, 2011 -Added instructions to beginning of file
#                            -Changed default port to /dev/ttyS0
#         0.5 - Feb 25, 2011 -Added code to load the second stage boot loader, H89LDR2.BIN
#                            -Added -p and -b switches to set the serial port and baud rate
#                             from the command line
#         0.6 - Oct 31, 2011 -Change command line with no switches to display entire help.
#         0.7 - Nov 27, 2011 -Added version and serial port info when run with empty command line
#         0.8 - Jan 09, 2012 -Fixed bugs with serial char exchange.
#                            -Fixed track display which never worked 100% 
#         0.8+3 Dec 13, 2025 -Update to Python3 by hackerb9
#
# Instructions:
#
# To use h8clxfer you must have the H89LDR by Dwight Elvey up and 
# running or have DD.COM running under CP/M.  Below are the links to the 
# software.  H89LDR / DD.COM is the side that runs on on the H8 or 
# H89 and h8clxfer talks to it.
#
# http://sebhc.lesbird.com/software
# http://sebhc.lesbird.com/software/Utilities/H89LDR9_README.TXT
#
# http://h8trans.cowlug.org/dd.html
#
# So the steps are:
#
# 0) Download the H89LDR utility from Dwight at the above link.
# 1) Key in the code on the front panel as per the readme.
# 2) Now run "h8clxfer.py -l -f H89LDR2.BIN", to connect and load the 
#    second half of the boot loader.
# 3) If the above was successful, put a disk in the first drive and 
#    issue the S command.
#
# You should now have a bootable disk you can use with h8clxfer.
# 
# You won't need to punch in the loader anymore.
#
#
# h8clxfer 
# ---------------------------------------------------------------------
# You will need to save this script and make it executable, from the 
# command prompt issue this command:  chmod +x h8clxfer.py.
#
# You must have python 3.x installed but virtually all modern Linux
# systems have Python installed by default. For time travellers stuck
# with Python 2, please use version 0.8 of this script from 2012.
#
# You must also have the Pyserial package installed.  On Ubuntu, Mint 
# and pretty much all other distributions based off of Debian you can
# install Pyserial with this command:  as root or with sudo, run: 
# "apt install python3-serial"
#
# For those of you using RPM based distros such as Fedora you can get
# pyserial from http://www.rpmfind.net just go there and search for
# pyserial.
#
# The last thing to do is set your serial port parameters. under Linux
# real serial ports as found on the motherboard are named
# /dev/ttyS0, /dev/ttyS1 for the first and second ports and so on.
# If you have a USB serial adapter it will be called /dev/ttyUSB0 or
# /dev/ttyUSB1 etc.  Caution: USB serial ports can change after the 
# system comes out of suspend, so suddenly what was /dev/ttyUSB0 is now 
# /dev/ttyUSB1.  Simply unplug the port wait a second or so and plug 
# it back in. 
#
# Now edit the h8clxfer.py file and find the "User modifiable settings"
# section and change the port then change the baud rate to match what 
# you have on your H8 or H89.  You can also set the serial port and 
# baud rate from the command line with the -p and -b switches.
#
# To get help using h8clxfer.py just type ./h8clxfer.py -h
# 
# Questions, bug reports and feature requests can go to the email 
# address above.  Thanks and enjoy.
#
# Protocol details
# ---------------------------------------------------------------------
# Receiving an image:
# -------------------
# PC (h89trans.com or h8clxfer) <-->    DD.COM or H89LDR2 on H8
#               'T'             -->             H8              Inform H8 we require volume number
#               PC              <--             '\0'    Send vol number to PC 0x00 for CP/M
#               PC              <--             'T'             Finished
#
#               'V'             -->             H8              Verify vol number
#               PC              <--             'V'
#
#               'R'             -->             H8              Tell H8 to setup for sending tracks
#       +->     'R'             -->             H8              Start of track - Loop until done
#       |       Trk             -->             H8              2560 bytes per track
#       +--     PC              <--             'R'             End of track
#
# Sending an image:
# -----------------
#               'V'             -->             H8              Inform H8 we are sending volume number
#               '\0'    -->             H8              Get Volume number
#               PC              <--             'V'             Inform PC we recieved it
#
#               'I'             -->             H8              Inform H8 we are sending Interleave
#               INTL    -->             H8              Get interleave
#               PC              <--             'I'             Inform PC we recieved it
#
#               'W'             -->             H8              Tell H8 to setup for incoming tracks
#       +->     'W'             -->             H8              Start of track - Loop until done
#       |       TRK             -->             H8              2560 bytes per track
#       +--     PC              <--             'W'             Got track okay
#       
#=============================================================================================


import sys, os, serial, string, binascii, time, getopt

# ------------- User modifiable settings ------------------------------
# Default Serial port settings
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 9600

# ------------- End of user modifiable settings -----------------------

VERSION = '0.8+3'

def load_second_stage_bootloader(filename):
        '''
; L - Loads the main loader to the H89/8 when the bootstrap program
;     is loaded by hand. If the main loader is already there
;     it says so. This is handy to check before other operations
;     that might hang. If you booted the H89/8 from the
;     "Boots Image Transfer" disk. This will check that it was
;     done correctly. If it returns with " Already Loaded" you are
;     OK. It prompts for the machine configuration to load the correct
;     code for your machine.'''
        try:
                sp = serial.Serial(SERIAL_PORT, BAUD_RATE, stopbits=serial.STOPBITS_TWO, timeout=1)
                print( "%s%s%s%s%s" % ("Serial port open [",SERIAL_PORT," ] [",BAUD_RATE,"]...") )
        except:
                print( "Fatal error - Could not open serial port...\n" )
                print( "Exiting..." )
                sys.exit(1)

        fp = open(filename,"rb")
        print( "\nUploading the second stage boot loader..." )
        sp.write(b'L')
        resp = b''
        resp = sp.read(1)
        if resp == b'?':
                print( "The second stage boot loader is already loaded..." )
                fp.close()
                sys.exit(0)
        
        c = fp.read()
        i = len(c) - 1
        while i > 0:
                sp.write(c[i])
                time.sleep(0.01)
                i = i - 1
                
        sp.write(b'L')
        resp = sp.read(1)
        if  resp == b'?':
                print( "Success!!  You may now save the boot loader to a disk..." )
                fp.close()
                sp.close()
                sys.exit(0)
        else:
                print( "Uploading failed, try reboot, check port settings etc..." )
                fp.close()
                sp.close()
                sys.exit(1)
                
                
def save_image_loader():
        '''             
; S - Save this image loader to disk as a stand alone boot
;      ( not HDOS ). The disk must be originally formatted
;      with V = 0. It returns a S when complete.'''
        try:
                sp = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
                print( "%s%s%s%s%s" % ("Serial port open [",SERIAL_PORT," ] [",BAUD_RATE,"]...") )
        except:
                print( "Fatal error - Could not open serial port...\n" )
                print( "Exiting..." )
                sys.exit(1)

        print( "Saving the boot loader to disk..." )
        set_volume_number(sp, "00")
        sp.write(b'S')
        resp = ""
        time.sleep(4)
        resp = sp.read(1)
        print( "RESP-> ",resp )
        if resp != b'S':
                print( "Saving the boot loader failed..." )
                print( "Please reboot your H8 and try again..." )
                sys.exit(1)

                
def set_interleave(sp,factor):
        '''
; I - Followed by a number 0,1,2 corresponding to a sector
;      interleaving of 1:1, 1:2, or 1:3. Other numbers will
;      cause incorrect formatting during writes. This has
;      effect on the W and S commands only.'''
        sp.write(b'I')
        sp.write(binascii.a2b_hex(factor))
        resp = ""
        #time.sleep(4)
        resp = sp.read(1)
        #print( "RESP-> ",resp )
        if resp != b'I':
                print( "Setting the interleave failed..." )
                print( "Please reboot your H8 and try again..." )
                sys.exit(1)
        print( "Set interleave [ ",factor," ]..." )
                
def set_volume_number(sp,vol):
        '''
; V - Sets the volume number for the various operations.
;      Check HDOS docs for useage of the Volume number.
;      It must receive the volume number as a non-ascii
;      byte as the next byte after the the V command. It
;      returns a V when complete.'''
        sp.write(b'V')
        sp.write(binascii.a2b_hex(vol))
        resp = ""
        resp = sp.read(1)
        #print( "RESP-> ",resp )
        if resp != b'V':
                print( "Setting the volume number failed..." )
                print( "Please reboot your H8 and try again..." )
                sys.exit(1)
        print( "Set volume number [ ",vol," ]..." )
        
def get_volume_number(typeofdisk,sp):
        '''
; C - Read the disk and returns the volume number if it is
;      an HDOS disk. If it is another type it would be an
;      indeterminate value.'''
        sp.write(b'T')
        vol = -1
        vol = sp.read(1)
        if vol == -1:
                print( "Getting the volume number failed..." )
                print( "Please reboot your H8 and try again..." )
                sys.exit(1)
        time.sleep(1)
        resp = sp.read(1)
        if resp != b'T':
                sys.exit(1)
        time.sleep(1)
        sp.write(b'V')
        resp = sp.read(1)
        if resp != b'V':
                print( "Getting the volume number failed..." )
                print( "Please reboot your H8 and try again..." )
                sys.exit(1)
        print( "Got volume number..." )
        return(vol)
        
        
def cmdline_read_floppy(typeofdisk,filename):
        '''
; R - Reads a disk image, using  V value. Each buffer will
;     begin transfer when a 'R' is received. Buffer size
;     is the same as used for W command. A character, other
;     than r will abort command. Buffer data is transfered
;     as 8 bit values. Response handshake is 'r' if error.'''
        print( "\nRead disk image from H8...\n" )
        
        image = ""
        fp = open(filename,"wb")
        track = 1

        try:
                sp = serial.Serial(SERIAL_PORT, BAUD_RATE, stopbits=serial.STOPBITS_TWO, timeout=None)
                print( "%s%s%s%s%s" % ("Serial port open [",SERIAL_PORT," ] [",BAUD_RATE,"]...") )
        except:
                print( "Fatal error - Could not open serial port...\n" )
                print( "Exiting..." )
                sys.exit(1)

        print( "\nTracks:" )
        vol = get_volume_number(typeofdisk,sp)
        
        sp.write(b'R')
        
        while track <= 40:
                sp.write(b'R')
                buf = sp.read(2560)
                resp = sp.read(1)                       #'R' if ok, 'r' is error

                if resp == b'r':
                        print( "\nThere was an error reading the disk, please try again..." )
                        print( "Please reboot your H8 and try again..." )
                        sys.exit(1)
                elif resp == b'R':
                        print( "%s%2s" % ("Track -> ",track) )
                        print(("\x1B[2F") )
                        track = track + 1
                        image = image + buf
                        
        print( "0\n\nFinished..." )
        fp.write(image)
        fp.close()      
        sp.close()
        sys.exit()



def cmdline_write_floppy(typeofdisk, filename):
        '''
; W - Write image to disk. When each buffer is loaded
;      it replies with W. Each buffer must start with 'W'
;      or it will abort to command. Buffer size must match.
;      It expects the V value to match the disk in the drive.
;      Buffer data is transfered as 8 bit value.'''
        print( "\nWrite disk image to H8...\n" )
        
        image = ""
        fp = open(filename,"rb")

        track = 1

        try:
                sp = serial.Serial(SERIAL_PORT, BAUD_RATE, stopbits=serial.STOPBITS_TWO, timeout=None)
                print( "%s%s%s%s%s" % ("Serial port open [",SERIAL_PORT," ] [",BAUD_RATE,"]...") )
        except:
                print( "Fatal error - Could not open serial port...\n" )
                print( "Exiting..." )
                sys.exit(1)

        if typeofdisk == "cpm":
                set_volume_number(sp,"00")
        else:
                fp.seek(0x900,0)
                vol = binascii.b2a_hex(fp.read(1))
                fp.seek(0,0)
                set_volume_number(sp,vol)

        set_interleave(sp,"00")

        time.sleep(1)
        
        print( "\nTracks:" )
        sp.write(b'W')
        time.sleep(1)
        
        while track <= 40:
                sp.write(b'W')
                buf = binascii.b2a_hex(fp.read(2560))
                sp.write(binascii.a2b_hex(buf))
                        
                resp = sp.read(1)                       #'W' if ok
                if resp != b'W':
                        print( "\nThere was an error writing the disk, please try again..." )
                        print( "Please reboot your H8 and try again..." )
                        sys.exit(1)
                else:
                        print( "%s%2s" % ("Track -> ",track) )
                        print(("\x1B[2F") )
                track = track + 1
                
        print( "0\n\nFinished..." )
        print( "I suggest you reboot your H8 if you want to read floppies reliably..." )
        fp.close()      
        sp.close()
        sys.exit()

def usage():
        print( "\n" )
        print( "========================================================================" )
        print( "h8clxfer.py - Version "+VERSION+" - Copyright George Farris, 2011. - GPLv3" )
        print( "              Serial Port - "+SERIAL_PORT+" ",BAUD_RATE,"bps" )
        print( "========================================================================\n" )

        print( "h8clxfer.py is used to read, write and load / save the boot loader on an H8" )
        print( "or H89 computer system.\n" )
        print( "To read a floppy image on the command line:" )
        print( "  ./h8clxfer.py -r -f filename" )
        print( "To write a floppy image on the command line:" )
        print( "  ./h8clxfer.py -w -t [cpm|hdos] -f filename" )
        print( "\nTo load the second stage boot loader, normally H89LDR2.BIN:" )
        print( "  ./h8clrxfer.py -l -f H89LDR2.BIN"  )
        print( "To save the bootloader to a disk run:" )
        print( "  ./h8clxfer.py -s" )
        print( "To change serial port and baud rate from the command line add these switches:" )
        print( "  ./h8clxfer.py -p [port] -b [rate]  to any command." )
        print( "\nExample:" )
        print( "  ./h8clxfer.py -p /dev/ttyS1 -b 19200 [rest of command r,w,s or l]\n" )


if __name__ == "__main__":
        
        myfilename = ""
        typeofdisk = ""
                        
        try:                                
                opts, args = getopt.getopt(sys.argv[1:], "lhf:rwst:p:b:", \
                        ["load","help","file","read","write","save","type","port","baud"])
        except getopt.GetoptError:
                usage()
                sys.exit(0)
        
        cmd = ""
        for opt, arg in opts:
                if opt in ("-h", "--help"):
                        usage()
                        sys.exit(0)                  
                elif opt in ("-l", "--load"):
                        cmd = 'load'
                elif opt in ("-f", "--file"):
                        myfilename = arg
                        print( "Filename " + myfilename )
                elif opt in ("-t", "--type"):
                        typeofdisk = arg
                        print( "Type of disk " + typeofdisk )
                elif opt in ("-p", "--port"):
                        SERIAL_PORT = arg
                elif opt in ("-b", "--baud"):
                        BAUD_RATE = arg
                elif opt in ("-w", "--write"):
                        cmd = 'write'
                elif opt in ("-r", "--read"):
                        cmd = 'read'
                elif opt in ("-s", "--save"):
                        cmd = 'save'
                        
                
        if cmd == 'read':
                cmdline_read_floppy(typeofdisk, myfilename)
                sys.exit(1)
        if cmd == 'write':
                if typeofdisk == "cpm" or typeofdisk == "hdos":
                        cmdline_write_floppy(typeofdisk,myfilename)
                else:
                        print( "\nYou must set a disk type with the -t switch.  The type can be" )
                        print( "cpm or hdos. Example -t cpm or -t hdos\n" )
                        sys.exit(1)
        if cmd == 'save':
                save_image_loader()
        if cmd == 'load':
                if myfilename == "":
                        print( "\nYou must provide the filename of the second stage boot loader" )
                        print( "with the -f switch, it is normally H89LDR2.BIN\n" )
                        sys.exit(1)
                else:
                        load_second_stage_bootloader(myfilename)
        if cmd == "":
                usage()
                #print( "You must choose -r, -w, -s or -l to read, or write a disk image," )
                #print( "save the bootloader or load the second stage boot loader..." )
                sys.exit(1)
        
        print( "Goodbye..." )
