;;; STAGE 1/2 SHIM LOADER by Hackerb9.
;;; Loads .ABS files from the serial port without booting from floppy.
;;; 
;;; Protocol is based on and compatible with Dwight Elvey's H89LDR.
;;; 
;;; | PC |		| H89 |			MEANING
;;;         'A' -->				PC: Are you alive?
;;;            <-- '?'     			H89: Yes, I am.
;;;         'B' -->     			PC: Ready for an ABS file?
;;;            <-- 'B'     			H89: Now receiving ABS file.
;;;         FFH --> 				PC: Magic: "Binary type"
;;;         00H --> 				PC: Magic: "ABS object"
;;;      ADDR L --> 				PC: Load the following program
;;;      ADDR H --> 				    into this memory address.
;;;    LENGTH L -->				PC: You will receive this many
;;;    LENGTH H -->				    bytes after the header.
;;;     ENTRY L -->				PC: When done, jump
;;;     ENTRY H -->				    to this location.
;;;        data -->				PC: Here's the .ABS file
;;;        ...					    ...
;;;        data -->
;;;            <-- 'B'				H89: LENGTH bytes received. 
;;; 					 	     I'm jumping to ENTRY.
;;; | PC |		| H89 |			MEANING


;;; Note that the 8 byte header is intended to be identical to HDOS's
;;; .ABS format, but of course you can load any arbitrary data you
;;; wish by prefixing it with the proper header.

;;; 	0: FFH	(binary type)
;;; 	1: 00H  (ABS object)
;;; 	2: ADDR Low
;;; 	3: ADDR High
;;; 	4: LENGTH Low
;;; 	5: LENGTH High
;;; 	6: ENTRYPOINT Low
;;; 	7: ENTRYPOINT High
;;; 
;;; Receives LENGTH bytes of data, places it starting at ADDR
;;; (increasing), and then jumps to ENTRYPOINT.
;;; 
;;; To load more than one ABS file in memory, change the ENTRYPOINT to
;;; 1400H for all files but the last. 1400H (024,000A) is the Floppy
;;; Drive RAM and where ABSLDR is stored by QUARTERSHIM. 

;;; SHORT USAGE via h89trans.py
;;; 
;;;  Press 'Q' to send QUARTERSHIM.BIN to BOOTSTRP
;;;  Press 'F' to send ABSLDR.BIN to QUARTERSHIM
;;;  Press 'O' to select an ABS file (e.g., GACTAGA.ABS)
;;;  Press 'A' to send it to ABSLDR and start it running



;;; USAGE EXPLANATION:
;;; 
;;; After a user has keyed in Dwight Elvey's BOOTSTRP.OCL at the
;;; Monitor, send the QUARTERSHIM.BIN from a host computer over the
;;; serial port instead of H89LDR2.ASM. All QUARTERSHIM does is unlock
;;; the Floppy RAM and load the next 1024 bytes (which is this
;;; program, ABSLDIR) from the serial port into addr 1400H and then
;;; executes it.
;;; 
;;; ABSLDIR will read yet another program over the serial port and
;;; execute it, similar to BOOTSTRP.ASM and QUARTERSHIM. The
;;; difference is that the next file's data is expected to be prefixed
;;; with an HDOS .ABS header. That allows the data to be loaded in any
;;; address in the H89 which is important since the Z80 didn't have
;;; proper position independent code. The ABS format also allows us to
;;; send programs of any length (not just 818 bytes) and to jump to
;;; any specified entry point when finished.
;;; 
;;; Since the incoming ABS file could be located anywhere in user RAM,
;;; this program runs from floppy RAM so it doesn't tromp upon itself.

;;; CREATING THE BIN FILE
;;; For cross assembly, use asmx -l -e -b1400H -C8080 ABSLDIR.ASM

;;; Version 0.5 January 5, 2026
;;; -- Seems to be working! Needs further testing, documentation.
;;; Version 0.4 December 21, 2025
;;; -- Now loading correctly at ORG 1400H, however it no longer works!
;;;    Handshaking problem?
;;; Version 0.3 December 17, 2025
;;; -- compile to ORG 1400H (Floppy RAM), presuming QUARTERSHIM will load us.
;;; Version 0.2 December 14, 2025
;;; -- read .ABS files directly using HDOS's 8-byte header.
;;; Version 0.1 December 14, 2025
;;; -- fixed up by b9 so it should actually work. Untested.
;;; Version 0.0 December 14, 2025
;;; -- major scaffolding from AI. Completely broken, but a start.
;;; -- requires H8-4/H89/Z89.

LP      EQU     0E0H 	; Base I/O address of 1st port on H-88-3 (340 Octal)
RX      EQU     LP	; Received byte
TX      EQU     LP	; Transmit byte
DVL     EQU     LP
DVH     EQU     LP+1
IER     EQU     LP+1
LCNTL   EQU     LP+3
MCNTL   EQU     LP+4
LSTAT   EQU     LP+5	; Line Status: Bit 0 is set if data has arrived.

FBEGIN	EQU	1400H		; Floppy RAM address
FSIZE	EQU	1800H-FBEGIN	; Num bytes in Floppy RAM (1K)

;;; This code lives in the Floppy RAM buffer which must be unlocked
;;; before it can be written to. (See QUARTERSHIM.ASM).
        ORG	FBEGIN	

	;; If Shift+Reset was hit, serial port needs to be reconfigured.
	CALL	SINT

;;; XXX Weirdly, the floppy starts up when I run this code. Is it
;;; because of where it is located in memory?

AWAIT:
	;; h89trans.py sends 'B' before sending an ABS file, expects 'B'.
	CALL	CHRIN
	CPI	'B'		; Is it 'B'?
	JZ	ABSLDR		; Yes, we can move forward.
        MVI	A,'?'		; Nope, reply with '?'.
        CALL	CHROUT
	JMP	AWAIT

ABSLDR:	
	;; Reply with 'B': We're ready to receive an ABS file.
        MVI	A,'B'
        CALL	CHROUT

	;; --- READ ABS HEADER --- 
HDR:	CALL    CHRIN       ; Ignore first two bytes of .ABS file
	CALL    CHRIN	    ; (XXX TODO: Maybe halt execution if not FF00?)

	CALL    CHRIN       ; Get Destination ADDR into DE
        MOV     E,A
        CALL    CHRIN
        MOV     D,A

        CALL    CHRIN       ; Get LENGTH into BC
        MOV     C,A
        CALL    CHRIN
        MOV     B,A

	CALL    CHRIN       ; Get ENTRY (jump) ADDR into HL
        MOV     L,A
        CALL    CHRIN
        MOV     H,A

	;; --- MAIN LOAD LOOP: Std 16-bit 8080 loop countdown ---
LOOP:	CALL    CHRIN       ; Read byte from serial into A
	STAX	D	    ; Store byte in destination (*DE)
	INX	D	    ; Next memory location
        DCX     B           ; Decrement LENGTH (BC) -- (Does not set Z-flag!)
	MOV	A,B
	ORA	C	    ; Are any bits of B or C set?
	JNZ     LOOP	    ; Nope, so get the next byte
	
	;; Let h89ldr.py know that we've received the file
        MVI	A,'B'
        CALL	CHROUT

	;; --- EXECUTE NEXT STAGE ---
        PCHL                ; Jump to the received code's ENTRY address.
	
;;; --- SERIAL I/O ROUTINES ---
CHRIN:	IN      LSTAT       ; Get serial port status 
        RAR		    ; Put "ready" bit in Carry
        JNC     CHRIN       ; Wait for char
        IN      RX	    ; Read the byte into A
        RET

CHROUT: 
        MOV 	D,A
CHROT2: IN 	LSTAT
        ANI 	60H		; Logical AND to get Transmitter Empty flags
        CPI 	60H		; Is UART ready to send?
        JNZ 	CHROT2
        MOV 	A,D
        OUT 	TX
        RET

SINT:  ; For H8-4 and H89 with LP
        XRA A
        Out LCNTL		; LINE CONTROL
        OUT IER			; NO INTERRUPTS
        OUT MCNTL		; INIT MODEM CONTROL
        DCR A			; SHOULD BE 'MVI A, 80H' BUT 0FFH OK
        OUT LCNTL
        MVI A, 0CH		; 9600 BAUD
        OUT DVL
        XRA A
        OUT DVH
        MVI A, 07H		; 8 BIT 2 STOPS
        OUT LCNTL
        IN LSTAT
        IN RX			; CLEAR ANY JUNK
        RET

;;; --- PAD GAP ---
;;; QUARTERSHIM expects a file exactly 1K in length, so reserve extra bytes.
PRGEND	DS	FBEGIN+FSIZE-PRGEND-1
	NOP


;;; NOTES

;;; 1. Stack pointer is initialized to end of memory by MTR at power-on.

;;; 2. CPU speed should not be an issue.
;;;    a. At 9600 baud, a byte arrives approximately every 1 ms.
;;;    b. Execution path from CHRIN to CHRIN is 54 T-states ≈ 0.027 ms.

;;; 3. The DS assembler macro is used to bulk out this program to fill
;;;    the 1K floppy buffer. This is so that future additions to this
;;;    program will not require changes to QUARTERSHIM.
