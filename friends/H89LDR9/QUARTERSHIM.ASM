;;; STAGE 1/4 SHIM LOADER by Hackerb9.
;;; 
;;; After a user has keyed in Dwight Elvey's Stage 0 BOOTSTRP.ASM at
;;; the Monitor, send this shim program from a host computer over the
;;; serial port instead of H89LDR2.ASM. It will unlock the Floppy
;;; Drive RAM and load the next stage (HALFSHIM) into that area and
;;; execute it.

;;; I'm using Floppy RAM because it is the only place I know of that
;;; will definitely not be clobbered when the next stage (HALFSHIM)
;;; loads up .ABS files to arbitrary locations in memory.


;;; CREATING THE BIN FILE
;;; For cross assembly, use asmx -l -e -b2329H -C8080 QUARTERSHIM.ASM

;;; USAGE
;;; After keying in BOOTSTRP.OCL, send the QUARTERSHIM binary from a PC:
;;; 	h8clxfer.py -l -f QUARTERSHIM.ASM.bin
;;; Once QUARTERSHIM is running, one can send HALFSHIM into the floppy RAM:
;;; 	h8clxfer.py -l -f HALFSHIM.ASM.bin
;;; After sending HALFSHIM, send an ABS file to start it running:
;;; 	h8clxfer.py -l -f GACTAGA.ABS

;;; Version 0.0 December 17, 2025
;;; -- Untested

LP      EQU     0E0H 	; Base I/O address of 1st port on H-88-3 (340 Octal)
RX      EQU     LP	; Receive buffer 
TX	EQU	LP	; Transmit buffer
IER     EQU     LP+1
LCNTL   EQU     LP+3
MCNTL   EQU     LP+4
LSTAT   EQU     LP+5	; Line Status: Bit 0 is set if data has arrived.
DVL     EQU     LP
DVH     EQU     LP+1

FBEGIN	EQU	1000H
FEND	EQU	17FFH

DBEND   EQU     265BH	; Data Block End address from BOOTSTRP.ASM
        ORG	2329H	; Matches with last byte of BOOTSTRP.ASM
	DB	00H,00H,00H,00H,00H,00H,00H ; Actual code starts at 2330H

	;; To unwrite protect floppy RAM (1000H to 17FFH):
	;; Set bit 7 of port 7F to 1. 
	IN	7FH
	ORI	80H
	OUT	7FH

	;; Serial port setup copied from BOOTSTRP.ASM... probably not necessary.
LDR:    XRA A
        OUT LCNTL       ; LINE CONTROL
        OUT IER         ; NO INTERRUPTS
        OUT MCNTL       ; INIT MODEM CONTROL
        DCR A           ; SHOULD BE 'MVI A, 80H' BUT 0FFH OK
        OUT LCNTL
        MVI A, 0CH      ; 9600 BAUD
        OUT DVL
        XRA A
        OUT DVH
        MVI A, 07H      ; 8 BIT 2 STOPS
        OUT LCNTL       ; THIS WILL BE 2313, MUST NOT BE 0FAH
        IN LSTAT
        IN RX           ; CLEAR ANY JUNK


	;; H89TRANS.COM and h89trans.py both send 'A' after loading this stage.
	CALL	GETCH
	;; Reply with '?' which lets H89TRANS know we're alive.
        MVI	A, '?'
        CALL	CHROUT

QSHIM:	
        LXI     D,FBEGIN
	LXI	B,1024		; 1K ought to be enough for anybody

	;; --- Standard 16-bit loop countdown ---
LOOP:	CALL    GETCH       ; Read byte from serial into A
	STAX	D	    ; Store byte in destination (*DE)
	INX	D	    ; Next memory location
	DCX     B           ; Decrement LENGTH (BC) -- (Does not set Z-flag!)
        MOV     A,B
        ORA     C	    ; Are any bits of B or C set?
        JNZ     LOOP	    ; Get the next byte

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
        IN LSTAT
        ANI 60H			; Logical OR with A register
        CPI 60H			; Is UART ready to send?
        JNZ CHROUT
        OUT TX
        RET

;;; --- PAD GAP ---
;;; Reserve enough bytes to match the length of H89LDR2.
PRGEND:	DS	DBEND-PRGEND-1
	NOP
;;;    The DS assembler macro is used to bulk out this program to
;;;    DBEND so that BOOTSTRP.ASM does need not be changed. This
;;;    program will be loaded into 2329H-265BH, same as H89LDR2.

;;; For debugging, return to Stage 0: R-Shift Break, S 43051 351, G 43000

