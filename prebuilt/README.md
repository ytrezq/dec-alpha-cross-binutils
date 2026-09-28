# Prebuilt examples

Windows AXP64 binaries — PE32+, machine type `0x0284` — produced by this
repository's converter, so the output can be inspected or run without
installing a cross toolchain. Rebuild them with `../tests/build-examples.sh`.

Running them needs the loader from the
[AXP64 runtime](https://github.com/ytrezq/test-windows-dec-alpha-builds),
whose `prebuilt/` has `winhost.exe` and the Alpha-compiled Win32 layer.

| file | source | what it is |
|---|---|---|
| `axp64asm.exe` | `tests/asm/axp64asm.s` | **hand-written DEC Alpha assembly**, self-checking |
| `hello-gui.exe` | `tests/hello-gui.c` | a Win32 GUI program in C |
| `LIB.dll`, `call_LIB.exe` | `tests/pv/` | the procedure-value experiment from [ABI.md](../ABI.md) |
| `LIBNT.dll`, `call_LIBNT.exe` | `tests/pv/` | the same, built with `--no-pv-thunk` |

## The assembly example

`axp64asm.s` is written in Alpha assembly, not compiled from C. It uses three
instructions no portable C would produce — `CMPBGE` for the classic Alpha
`strlen`, `ZAPNOT` for byte-lane masking, and `PERR` and `MINUB8` from the
Motion Video Instruction extension — then checks all four results against
their expected values and sets its exit code accordingly.

```sh
wine winhost.exe -k axp64asm.exe guest/KERNEL32.dll
```

```
AXP64, hand-written Alpha assembly
cmpbge strlen  = 0x0000000000000012
perr   (MVI)   = 0x0000000000000008
zapnot         = 0x0000000050607080
minub8 (MVI)   = 0x1020304050607080
all four match the expected values
[winhost] guest exit(0)
```

1,136 Alpha instructions, translated to x86-64 and run.

## The procedure-value experiment

The two `call_*` programs are the same source built against the same DLL
source, differing only in whether the exports carry a pv-setup thunk. Run
each and compare — this is the measurement behind [ABI.md](../ABI.md) §2:

```sh
wine winhost.exe -k -c call_LIB.exe   LIB.dll   guest/KERNEL32.dll
wine winhost.exe -k -c call_LIBNT.exe LIBNT.dll guest/KERNEL32.dll
```

`LIB.dll` reports its global at `0x60004000` on both calls. `LIBNT.dll` is
right on the first and, on the second — the one made the way Microsoft's
AXP64 code makes indirect calls — computes the address as `0x00402318`,
inside the *caller's* image, then faults.

## Provenance

Everything here is built from source in this repository by stock
`alpha-linux-gnu` GCC and binutils. No Microsoft code or binary is involved.
