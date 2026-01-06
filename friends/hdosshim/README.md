# HDOS Shim 

This is a so far failing attempt to make shims which can be sent to
ABSLDR to setup RAM as if the machine was running HDOS. The .sys files
have been converted into peculiar `.abs` files by modifying the 8 byte
header:

* MAGIC: First two bytes changed to 0FFH and 00 (Binary, ABS object).
* ADDRESS: Second two bytes left unchanged.
* LENGTH: Third two bytes left unchanged.
* ENTRY: Fourth two bytes set to 00 and 14H. 

Since 1400H is the address of ABSLDR, after these shims are loaded
into memory by ABSLDR, instead of being executed, ABSLDR will restart
and wait for another `.abs` file.


### Why is HDOS.SYS failing? 

While I can load normal .ABS files into their correct location,
loading HDOS.SYS fails, probably because it is loading it into memory
while that memory is being used as a stack. In particular, address
2032H gets written to memory over and over again, like a call stack.
Attempting to even write to the those bytes from the monitor fails.
After typing the first nybble to change byte 2036H, the monitor drops
back down to the H: prompt.

``` shell
H: RADIX HEXADECIMAL
H: SUBSTITUTE 2032
```

### Why did writing address 38H fail?

I want to change the interrupt vector "RST 7" which is at memory
location 38H. However, writing directly to it fails. It probably needs
to be unlocked using OUT commands.   
