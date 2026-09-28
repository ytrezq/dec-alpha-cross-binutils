# dec-alpha-cross-binutils

A cross toolchain that produces **Windows AXP64** binaries — 64-bit DEC
Alpha PE32+, machine type `0x0284` — from C, on a modern Linux host.

**What this is, precisely:** not a fork of binutils. It is the distribution's
stock `alpha-linux-gnu` GCC and binutils, plus the missing piece — an
**ELF → PE32+ converter** and a build driver. That missing piece is the whole
problem: binutils has no `alpha-pe` target and LLVM dropped its Alpha
backend in 3.0, so no toolchain in existence emits Alpha PE files.

## The trick

Rather than write an Alpha linker, let `alpha-linux-gnu-ld` resolve every
Alpha relocation — `GPDISP`, `LITERAL`, `GPREL*` — against a fixed image
base, then wrap the linked image in a PE container.

The key observation is that the two object formats already agree where it
matters. The Alpha ABI reaches every external symbol indirectly, through a
64-bit GOT slot addressed off `gp`. A PE import address table is exactly
that: a table of 64-bit slots the loader fills in. So the PE import directory
simply points its `FirstThunk` at the GOT the linker already built, and
nothing needs relocating.

Every format decision was checked against `depends.dll`, a genuine AXP64
binary: machine `0x0284`, PE32+ magic `0x20B`, a 240-byte optional header,
8-byte IAT entries, section alignment `0x2000`.

## Use

```sh
sudo apt install gcc-alpha-linux-gnu binutils-alpha-linux-gnu python3

# an executable
./mkaxp64.sh -o hello.exe --base 0x400000 --entry entry \
    --import "USER32.dll:MessageBoxA" \
    --import "KERNEL32.dll:ExitProcess" \
    tests/hello-gui.c

# a DLL
./mkaxp64.sh -o MYLIB.dll --dll --base 0x10000000 --entry DllMain \
    --export Foo --export Bar mylib.c
```

| option | meaning |
|---|---|
| `-o FILE` | output PE |
| `--base ADDR` | image base (no relocations are emitted, so this is where it must load) |
| `--entry SYM` | entry point symbol |
| `--dll` | build a DLL rather than an executable |
| `--import "DLL:a,b,c"` | imports from `DLL` |
| `--export SYM` | one export by name |
| `--export-file F` | one export per line |
| `--export-ord F` | sparse ordinal exports, `ordinal=symbol` per line, `:data` for data exports |

Ordinal-only and data exports are supported because real AXP64 DLLs use
them: `MFC42.DLL` exports several thousand entries by ordinal alone, over a
sparse export address table.

## Layout

| | |
|---|---|
| `mkaxp64.sh` | the driver: compile, link at a fixed base, convert |
| `elf2pe.py` | the converter — ELF image in, PE32+ out |
| `axp64.ld.in` | the linker script template |
| `tests/hello-gui.c` | a small Win32 GUI program to build |

## Does this actually port the ABI?

No — not by itself, and that is the interesting part. `alpha-linux-gnu-gcc`
targets the SysV Alpha ABI; Windows AXP64 uses Microsoft's Alpha calling
standard. Rewrapping the container changes neither.

**[ABI.md](ABI.md)** measures the difference against a genuine
Microsoft-built AXP64 binary rather than asserting it. Short version: the
argument registers, return registers, callee-saved set and varargs layout are
identical; `gp` and the procedure-value register are not, and unwind data is a
real gap. `elf2pe.py` closes the procedure-value difference with a four-
instruction thunk per export — `tests/pv/` is a controlled experiment showing
what breaks without it.

## Limitations

* No base relocations, so each image must load at its preferred base. Every
  module in a set therefore gets a distinct base.
* No `.pdata` unwind information, so structured exception handling is not
  available to the produced code.
* C only. There is no Alpha C++ ABI support here.

## Related

* **[test-windows-dec-alpha-builds](https://github.com/ytrezq/test-windows-dec-alpha-builds)** —
  the runtime that executes what this produces, on x86-64 under unmodified
  Wine.
* **[dec-alpha-mfc42-partial-reverse-engineering](https://github.com/ytrezq/dec-alpha-mfc42-partial-reverse-engineering)**
