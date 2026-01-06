; HDOS System Call Vector
; Redirects RST 7 (RST 38H) to the resident HDOS handler.
	;;  This doesn't work as address 0038 isn't writeable.
	ORG 0038H
	JMP 2011H    ; Jump to HDOS SCALL handler entry point
	
	HLT
	
