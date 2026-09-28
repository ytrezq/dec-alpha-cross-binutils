# The procedure-value experiment

Shows that ELF → COFF conversion alone does not port the Alpha calling
convention, by isolating the single register that differs.

`lib.c` is an ordinary gcc-built DLL: `probe()` reads a global, so its
address is loaded out of the GOT, i.e. through `gp`, i.e. through `$27`.

`caller.c` calls it twice:

1. the SysV way — gcc puts the callee's address in `$27` itself;
2. the MSVC way — target in `$0`, `jsr $26,($0)`, with `$27` left holding an
   unrelated pointer, which is what Microsoft's AXP64 code does at all 1,321
   of its indirect call sites.

Build the library both ways and run each against its caller:

```sh
../../mkaxp64.sh -o LIB.dll   --dll --base 0x60000000 --entry DllMain \
    --import "winhost:__mfc_trace" --export probe lib.c
../../mkaxp64.sh -o LIBNT.dll --dll --base 0x60100000 --entry DllMain \
    --no-pv-thunk \
    --import "winhost:__mfc_trace" --export probe lib.c
```

`LIB.dll` reports the global at its true address and returns the right value
on both calls. `LIBNT.dll` is correct on call 1 and, on call 2, computes the
global's address inside the *caller's* image instead, then faults on the next
load through the corrupted `gp`.

See `../../ABI.md` §2.
