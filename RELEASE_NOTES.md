# v0.1.0 — AXP64 cross toolchain

Produces **Windows AXP64** binaries — 64-bit DEC Alpha, PE32+ machine type
`0x0284` — from C or Alpha assembly, on a modern Linux host.

Not a fork of binutils: it drives the distribution's stock `alpha-linux-gnu`
GCC and binutils and supplies the piece that does not exist anywhere —
an **ELF → PE32+ converter** — because binutils has no `alpha-pe` target and
LLVM dropped its Alpha backend in 3.0.

## Assembly in, AXP64 out

```sh
./mkaxp64.sh -o axp64asm.exe --base 0x400000 --entry entry \
    --import "KERNEL32.dll:OutputDebugStringA,ExitProcess" \
    tests/asm/axp64asm.s
```

`mkaxp64.sh` takes `.c`, `.s`, `.S` or a pre-built `.o`.

## Assets

`prebuilt/examples/` (also in the source archive) carries these already
built, so the output can be inspected or run without a cross toolchain:

| file | what it is |
|---|---|
| `axp64asm.exe` | hand-written DEC Alpha assembly — `CMPBGE`, `ZAPNOT`, and `PERR`/`MINUB8` from the MVI extension — self-checking, exits 0 |
| `hello-gui.exe` | a Win32 GUI program in C |
| `LIB.dll` + `call_LIB.exe` | the procedure-value experiment from `ABI.md` |
| `LIBNT.dll` + `call_LIBNT.exe` | the same, built with `--no-pv-thunk`, which faults |

Running them needs the loader from the
[AXP64 runtime](https://github.com/ytrezq/test-windows-dec-alpha-builds).

## ABI

`alpha-linux-gnu-gcc` targets the SysV Alpha ABI; Windows AXP64 uses
Microsoft's Alpha calling standard, and rewrapping the container does not
change that. [ABI.md](ABI.md) measures the difference against a genuine
Microsoft-built AXP64 binary: the argument registers, return registers,
callee-saved set and varargs layout are identical; `gp` and the
procedure-value register are not; unwind data (`.pdata`, hence SEH) is a real
gap. The two `call_*` binaries above reproduce the central measurement.

## Provenance

A converter and a build driver. No Microsoft code, no disassembly of any, and
no Microsoft binary redistributed.
