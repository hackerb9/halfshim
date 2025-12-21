;;; STAGE 1/2 SHIM LOADER by Hackerb9.
;;; 
;;; Expects an 8 byte header similar to HDOS's .ABS format
;;; 
;;; 	0: FFH	(binary type)
;;; 	1: 00H  (ABS object)
;;; 	2: ADDR L
;;; 	3: ADDR H
;;; 	4: LENGTH L
;;; 	5: LENGTH H
;;; 	6: ENTRYPOINT L
;;; 	7: ENTRYPOINT H
;;; 
;;; Places received data starting at ADDR and then jumps to ENTRYPOINT.

;;; SHORT USAGE:
;;; 
;;; 	h8clxfer.py -l -f QUARTERSHIM.ASM.bin
;;; 	h8clxfer.py -l -f HALFSHIM.ASM.bin
;;; After sending HALFSHIM, send an ABS file to start it running:
;;; 	h8clxfer.py -l -f GACTAGA.ABS

;;; USAGE EXPLANATION:
;;; 
;;; After a user has keyed in Dwight Elvey's BOOTSTRP.OCL at the
;;; Monitor, send the QUARTERSHIM.BIN from a host computer over the
;;; serial port instead of H89LDR2.ASM. All QUARTERSHIM does is unlock
;;; the Floppy RAM and load the next 1024 bytes (which is this
;;; program, HALFSHIM) from the serial port into addr 1400H and then
;;; executes it.
;;; 
;;; HALFSHIM will read yet another program over the serial port and
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
;;; For cross assembly, use asmx -l -e -b1400H -C8080 HALFSHIM.ASM

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
LSTAT   EQU     LP+5	; Line Status: Bit 0 is set if data has arrived.

FBEGIN	EQU	1400H		; Floppy RAM address
FSIZE	EQU	1800H-FBEGIN	; Num bytes in Floppy RAM (1K)

;;; This code lives in the Floppy RAM buffer which must be unlocked
;;; before it can be written to. (See QUARTERSHIM.ASM).
        ORG	FBEGIN	

	;; H89TRANS.COM and h89trans.py both send 'A' after loading the second stage.
	CALL	GETCH
	;; Reply with '?' which lets H89TRANS know we're alive.
        MVI	A,'?'
        CALL	CHROUT

	;; --- READ HEADER --- 
SHIM:	CALL    GETCH       ; Ignore first two bytes of .ABS file
	CALL    GETCH	    ; (TODO: Maybe halt execution if not FF00?)

	CALL    GETCH       ; Get Destination ADDR into DE
        MOV     E,A
        CALL    GETCH
        MOV     D,A

        CALL    GETCH       ; Get LENGTH into BC
        MOV     C,A
        CALL    GETCH
        MOV     B,A

	CALL    GETCH       ; Get Jump ADDR into HL
        MOV     L,A
        CALL    GETCH
        MOV     H,A

	;; --- MAIN LOAD LOOP: Std 16-bit 8080 loop countdown ---
LOOP:	CALL    GETCH       ; Read byte from serial into A
	STAX	D	    ; Store byte in destination (*DE)
	INX	D	    ; Next memory location
        DCX     B           ; Decrement LENGTH (BC) -- (Does not set Z-flag!)
	MOV	A,B
	ORA	C	    ; Are any bits of B or C set?
	JNZ     LOOP	    ; Nope, so get the next byte
	
	;; --- EXECUTE NEXT STAGE ---
        PCHL                ; Jump to the received code.

;;; --- SERIAL INPUT ROUTINE ---
;;; (Presumes serial port already configured by Stage 0 loader.)
GETCH:	IN      LSTAT       ; Get serial port status 
        RAR		    ; Put "ready" bit in Carry
        JNC     GETCH       ; Wait for char
        IN      RX	    ; Read the byte into A
        RET

CHROUT: 
        MOV 	D,A
CHROT2: IN 	LSTAT
        ANI 	60H		; Logical AND to get not-ready bits
        CPI 	60H		; Is UART ready to send?
        JNZ 	CHROT2
        MOV 	A,D
        OUT 	TX
        RET

;;; --- PAD GAP ---
;;; QUARTERSHIM expects a file exactly 1K in length, so reserve extra bytes.
PRGEND	DS	FBEGIN+FSIZE-PRGEND-1
	NOP


;;; NOTES

;;; 1. Stack pointer is initialized to end of memory by MTR at power-on.

;;; 2. CPU speed should not be an issue.
;;;    a. At 9600 baud, a byte arrives approximately every 1 ms.
;;;    b. Execution path from GETCH to GETCH is 54 T-states ≈ 0.027 ms.

;;; 3. The DS assembler macro is used to bulk out this program to fill
;;;    the 1K floppy buffer. This is so that future additions to this
;;;    program will not require changes to QUARTERSHIM.
