;;; STAGE 1/4 SHIM LOADER by Hackerb9.
;;; Comes after Stage-0 but before the real loader.

;;; After a user has keyed in Dwight Elvey's BOOTSTRP.ASM (Stage 0) at
;;; the Monitor, send this shim program from a host computer over the
;;; serial port instead of H89LDR2.ASM. It will unlock the Floppy
;;; Drive RAM, wait for the letter 'F' over the serial port, load the
;;; next stage loader into the Floppy RAM area, and execute it.

;;; Why Floppy RAM? If the next stage is ABSLDR, it will load up .ABS
;;; files to arbitrary locations in memory. Floppy RAM is a safe place
;;; for ABSLDR to live without worry that it will clobber itself.

;;; CREATING THE BIN FILE
;;; For cross assembly, use asmx -l -e -b2329H -C8080 QUARTERSHIM.ASM

;;; USAGE from the h89trans.py program
;;; After keying in BOOTSTRP.OCL, send the QUARTERSHIM binary from a PC:
;;; 	type 'Q' to send QUARTERSHIM.BIN
;;; Once QUARTERSHIM is running, one can send ABSLDR into the floppy RAM:
;;; 	type 'F' to send ABSLDR.BIN
;;; After sending ABSLDR, send an ABS file to start it running:
;;; 	type 'O' to open an ABS file
;;; 	type 'GACTAGA.ABS' (the ABS filename to send) and hit Enter
;;; 	type 'A' to send it to ABSLDR.

;;; NOTES FOR WRITING YOUR OWN NEXT STAGE (instead of ABSLDR)
;;; * Loads at 1400H to 17FFH
;;;   * ORG 1400H
;;;   * Exactly 1024 bytes long. (Use DS macro).
;;; * Can be sent to QUARTERSHIM using h89ldr.py's 'F'loppy-RAM command.

;;; Version 0.2 December 22, 2025
;;; -- Seems to work correctly. 
;;; Version 0.1 December 21, 2025
;;; -- Runs, but forgot to receive the loader in reverse order.
;;; Version 0.0 December 17, 2025
;;; -- Untested

LP      EQU     0E0H 	; Base I/O address of 1st port on H-88-3 (340 Octal)
RX      EQU     LP	; Receive buffer 
TX	EQU	LP	; Transmit buffer
DVL     EQU     LP
DVH     EQU     LP+1
IER     EQU     LP+1
LCNTL   EQU     LP+3
MCNTL   EQU     LP+4
LSTAT   EQU     LP+5	; Line Status: Bit 0 is set if data has arrived.

FBEGIN	EQU	1400H		; Floppy RAM address
FEND	EQU	17FFH		; Last byte of RAM address
FSIZE	EQU	FEND-FBEGIN+1	; Num bytes in Floppy RAM (1K)

DBEND   EQU     265BH		; Data Block End address from BOOTSTRP.ASM

        ORG	2329H		; Matches with last byte of BOOTSTRP.ASM
	DB	00H,00H,00H,00H,00H,00H,00H ; Actual code starts at 2330H

;;; To unlock the floppy RAM (1000H to 17FFH), set bit 7 of port 7F to 1. 
;;; (See table at end).
	MVI	A,80H
	OUT	7FH

	;; If Shift+Reset was hit, serial port needs to be reconfigured.
	CALL	SINT

	;; H89TRANS will send 'A' to check if we're alive, expects '?'.

	;; h89trans.py sends 'F' and waits for 'F' before sending the
	;; next stage. It then waits for a 2nd 'F' to know we received it.
COMMAND:
	CALL	CHRIN
	CPI	'F'		; 'F' = 46H
	JZ	QSHIM
        MVI	A,'?'		; '?' = 3FH
        CALL	CHROUT
	JMP	COMMAND

QSHIM:	
	CALL	CHROUT		; Send 'F' to let h89trans.py we're ready 
        LXI     D,FEND		; DE = Address to store next byte (counts down)
	LXI	B,FSIZE		; BC = Length of program in bytss

	;; --- Standard 16-bit loop countdown ---
LOOP:	CALL    CHRIN       ; Read byte from serial into A
	STAX	D	    ; Store byte in destination (*DE)
	DCX	D	    ; Next memory location
	DCX     B           ; Decrement LENGTH (BC) -- Does not set Z-flag!
        MOV     A,B
        ORA     C	    ; Are any bits of B or C set?
        JNZ     LOOP	    ; Get the next byte

	;; Relock the Floppy RAM (OUT 7F, 0)
	XRA	A
	OUT	7FH

	;; Let h89trans.py know that we've received all the bytes
	MVI	A,'F'		; 'F' = 46H
	CALL 	CHROUT

	;; --- EXECUTE NEXT STAGE ---
        JMP	FBEGIN

;;; --- SERIAL INPUT ROUTINE ---
;;; (Presumes serial port already configured by Stage 0 loader.)
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
        Out LCNTL      ; LINE CONTROL
        OUT IER        ; NO INTERRUPTS
        OUT MCNTL      ; INIT MODEM CONTROL
        DCR A           ; SHOULD BE 'MVI A, 80H' BUT 0FFH OK
        OUT LCNTL
        MVI A, 0CH      ; 9600 BAUD
        OUT DVL
        XRA A
        OUT DVH
        MVI A, 07H      ; 8 BIT 2 STOPS
        OUT LCNTL
        IN LSTAT
        IN RX           ; CLEAR ANY JUNK
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
