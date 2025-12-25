;;; STAGE 1/4 SHIM LOADER by Hackerb9.
;;; Comes after Stage-0 but before the real loader.

;;; After a user has keyed in Dwight Elvey's BOOTSTRP.ASM (Stage 0) at
;;; the Monitor, send this shim program from a host computer over the
;;; serial port instead of H89LDR2.ASM. It will unlock the Floppy
;;; Drive RAM and load the next stage loader into that area and
;;; execute it.

;;; I'm using Floppy RAM because it is the only place I know of that
;;; will definitely not be clobbered when the next stage is HALFSHIM
;;; which can load up .ABS files to arbitrary locations in memory.

;;; CREATING THE BIN FILE
;;; For cross assembly, use asmx -l -e -b2329H -C8080 QUARTERSHIM.ASM

;;; USAGE
;;; After keying in BOOTSTRP.OCL, send the QUARTERSHIM binary from a PC:
;;; 	h8clxfer.py -l -f QUARTERSHIM.ASM.bin
;;; Once QUARTERSHIM is running, one can send HALFSHIM into the floppy RAM:
;;; 	h8clxfer.py -l -f HALFSHIM.ASM.bin
;;; After sending HALFSHIM, send an ABS file to start it running:
;;; 	h8clxfer.py -l -f GACTAGA.ABS

;;; NOTES FOR WRITING YOUR OWN NEXT STAGE
;;; * Loads at 1400H to 17FFH
;;;   * ORG 1400H
;;;   * Exactly 1024 bytes long. (Use DS macro).
;;; * If sent by h89ldr

;;; Version 0.2 December 22, 2025
;;; -- Seems to work correctly. 
;;; Version 0.1 December 21, 2025
;;; -- Runs, but forgot to receive the loader in reverse order.
;;; Version 0.0 December 17, 2025
;;; -- Untested

LP      EQU     0E0H 	; Base I/O address of 1st port on H-88-3 (340 Octal)
RX      EQU     LP	; Receive buffer 
TX	EQU	LP	; Transmit buffer
LSTAT   EQU     LP+5	; Line Status: Bit 0 is set if data has arrived.

FBEGIN	EQU	1400H		; Floppy RAM address
FEND	EQU	17FFH		; Last byte of RAM address
FSIZE	EQU	FEND-FBEGIN+1	; Num bytes in Floppy RAM (1K)


DBEND   EQU     265BH	; Data Block End address from BOOTSTRP.ASM
        ORG	2329H	; Matches with last byte of BOOTSTRP.ASM
	DB	00H,00H,00H,00H,00H,00H,00H ; Actual code starts at 2330H

;;; To unlock the floppy RAM (1000H to 17FFH), set bit 7 of port 7F to 1. 
;;; (See table at end).
	MVI	A,8FH
	OUT	7FH

LDR:	
	;; H89TRANS.COM and h89trans.py send 'A' after loading this stage.
	CALL	GETCH
	;; Reply with '?' which lets H89TRANS know we're alive.
        MVI	A,3FH		; ord('?') = 3FH
        CALL	CHROUT

QSHIM:	
        LXI     D,FEND	; DE = Address to store next byte (counts down)
	LXI	B,FSIZE	; BC = Length of program in bytss

	;; --- Standard 16-bit loop countdown ---
LOOP:	CALL    GETCH       ; Read byte from serial into A
	STAX	D	    ; Store byte in destination (*DE)
	DCX	D	    ; Next memory location
	DCX     B           ; Decrement LENGTH (BC) -- Does not set Z-flag!
        MOV     A,B
        ORA     C	    ; Are any bits of B or C set?
        JNZ     LOOP	    ; Get the next byte

	;; Relock the Floppy RAM
	XRA	A
	OUT	7FH

	;; Let h89trans.py know that we've arrived
	MVI	A,3FH		; 3F = '?'
	CALL 	CHROUT

	;; --- EXECUTE NEXT STAGE ---
        JMP	FBEGIN

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
        ANI 	60H		; Logical AND to get Transmitter Empty flags
        CPI 	60H		; Is UART ready to send?
        JNZ 	CHROT2
        MOV 	A,D
        OUT 	TX
        RET

;;; --- PAD GAP ---
;;; Reserve enough bytes to match the length of H89LDR2.
PRGEND:	DS	DBEND-PRGEND-1
	NOP
;;;    The DS assembler macro is used to bulk out this program to
;;;    DBEND so that BOOTSTRP.ASM does need not be changed. This
;;;    program will be loaded into 2329H-265BH, same as H89LDR2.


;;; Notes on writing to port 7F
;;; 
;;; 	    OUT Function		Description
;;; 
;;; Bit 0   Drive Select 0	Set to 1 to enable Drive 0 (SY0:).
;;; Bit 1   Drive Select 1	Set to 1 to enable Drive 1 (SY1:).
;;; Bit 2   Drive Select 2	Set to 1 to enable Drive 2 (SY2:).
;;; 
;;; Bit 3   Motor On		Set to 1 to start the floppy drive motors. 
;;; 	    			All motors on the controller spin together.
;;; 
;;; Bit 4   			Not used on standard H17.
;;; Bit 5   			Not used on standard H17.
;;; Bit 6   			Not used on standard H17.
;;; 
;;; Bit 7   RAM Write Protect	On power-up/reset this bit is 0 which 
;;; 				write-protects the Bank 0 System RAM (0-8K). 
;;;				Set this to 1 to allow writing to the lower 8K.
;;; 				In particular, Floppy RAM is from 1400-17FF
;;;
;;; NB: The bits for IN on port 7F have completely different meanings!


;;; For debugging, return to Stage 0: R-Shift Break; S 43051 351; G 43000
;;; 				     or Hexadecimal: S 2329 E9;   G 2300
