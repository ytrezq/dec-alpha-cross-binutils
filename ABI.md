# SysV Alpha vs Windows AXP64: what actually differs

Converting an ELF container into Microsoft's COFF variant does not port a
calling convention. `alpha-linux-gnu-gcc` targets the SysV/Tru64 Alpha ABI;
Windows AXP64 uses Microsoft's Alpha calling standard. They are not the same
document, and a file-format transformation cannot make them so.

So: *which* parts differ, and *which* of those are load-bearing? This is
measured, not asserted. Every number below comes from static analysis of a
genuine Microsoft-built AXP64 binary — `depends.exe` from the Windows 2000
beta Support Tools, PE32+ machine `0x0284`, 65,097 instructions of `.text` —
compared against this toolchain's own output. The scripts are in `tools/`.

**Reproduce it:**

```sh
python3 tools/peabi.py   <some-axp64.exe>     # conventions
python3 tools/pdata.py   <some-axp64.exe>     # unwind tables
```

## Summary

| | MSVC AXP64 | `alpha-linux-gnu-gcc` | same? |
|---|---|---|---|
| integer argument registers | `$16`–`$21` | `$16`–`$21` | yes |
| float argument registers | `$f16`–`$f21` | `$f16`–`$f21` | yes |
| return value | `$0` / `$f0` | `$0` / `$f0` | yes |
| callee-saved | `$9`–`$15`, `$26` | `$9`–`$15`, `$26` | yes |
| caller-allocated argument home area | none | none | yes |
| varargs register spill | into the callee's own frame | into the callee's own frame | yes |
| **`$29` (gp)** | **never used at all** | **required, reloaded per function** | **no** |
| **`$27` (pv) at entry** | **only on the import path** | **always required** | **no** |
| **unwind data** | **`.pdata`, mandatory for SEH** | **none emitted** | **no** |

Three real divergences. The first two have a single shared cause; the third
is unfixed and is stated as a limitation, not papered over.

## 1. `gp` does not exist on Windows AXP64

In 65,097 instructions of Microsoft's `.text`, register `$29` is **written 0
times and read 0 times**. The Windows Alpha calling standard has no global
pointer: every static address is materialised inline.

This toolchain's `MFC42.dll`, over 13,164 instructions, writes `$29` 1,974
times and reads it 1,769 times, because SysV Alpha reaches statics through a
GOT addressed off `gp`.

That asymmetry is what makes the bridge possible at all. gcc code *needs* gp;
MSVC code does not *care* what is in `$29`. So gcc may clobber it freely, and
the only requirement is that gp be correct on entry to each gcc function.

## 2. `gp` comes from `$27`, and MSVC only sets `$27` on one path

gcc opens (almost) every global function with the `ldgp` idiom:

```
ldah $29, hi($27)
lda  $29, lo($29)
```

so `gp = $27 + K`, with `K` fixed at link time. This is only correct when
`$27` holds **this function's own entry address** — the SysV procedure-value
contract. 409 of the 414 exported functions in `MFC42.dll` begin this way,
and 409 of them then dereference `gp` (1,224 loads). Get `$27` wrong and they
read from the wrong address.

Does MSVC provide it? Tabulating every control transfer in `depends.exe`:

| form | count | meaning |
|---|---:|---|
| `jsr $26,($0)` | 1,222 | indirect/virtual call — `$27` untouched |
| `ret $31,($26)` | 726 | return |
| `jmp $31,($27)` | 431 | **import stub tail-jump** |
| `jsr $26,($1)` and other temporaries | 93 | indirect call — `$27` untouched |

**Zero** indirect calls pass the target in `$27`. In 1,320 of 1,321 indirect
call sites `$27` is not written anywhere in the six preceding instructions.
As far as MSVC is concerned `$27` is just `t12`, an ordinary temporary
(1,852 writes, 1,879 reads, none of them procedure values).

But look at the 431 `jmp $31,($27)` sites. All 431 have an identical shape:

```
sll  $27, 32, $27
ldah $27, hi($27)
ldq  $27, lo($27)     ; <- $27 = *IAT_slot, the callee's real address
jmp  $31, ($27)       ; <- tail-jump, callee entered with pv correct
```

All 431 computed addresses land inside the import address table
(`0x442000`–`0x4434b0`); 414 of them are `MFC42.DLL` slots, matching the 414
thunked exports one for one.

**Microsoft's import stub is a procedure descriptor.** It loads the callee's
address into `$27` and tail-jumps — which happens to be exactly the SysV `pv`
contract. Every MSVC → gcc transfer through the import table therefore
satisfies gcc's `ldgp` for free.

### This is luck, not compatibility

To show the mechanism is real rather than assumed, `elf2pe.py --no-pv-thunk`
exports raw gcc entry addresses, and `tests/pv/` contains a caller written in
the shape MSVC emits — target in `$0`, `jsr $26,($0)`, `$27` left holding an
unrelated temporary:

```
                          address of a global computed inside the callee
with the pv-setup thunk   0x60004000   correct
without it                0x00402318   wrong, and inside the *caller's* image
                                       -> next GOT load reads address 0
                                       -> access violation
```

Same DLL, same source, same call. Only `$27` differs.

So `elf2pe.py` emits a four-instruction pv-setup thunk for every exported
function:

```
br   $27, .+4         ; pv = PC
ldah $27, hi($27)
lda  $27, lo($27)     ; pv = &target
jmp  $31, ($27)
```

and `make_pv_thunk()` does the same for vtable slots handed to foreign code,
which the export table cannot cover.

### Honest scope

With `depends.exe` specifically, **both shims can be switched off and the
application still renders pixel-identically.** Its MSVC → gcc transfers all
go through the import table, and the import stub already sets `$27`. No data-
resident pointer in the image (0 of 3,336 `.rdata` code pointers, 0 of 4 in
`.data`) targets an import stub, so no `jsr $26,($0)` in that binary lands
directly on a gcc entry.

The thunks are therefore **correct and necessary in general** — the
controlled test above shows what happens without them — but for this one
binary they are defensive. Saying otherwise would be overclaiming.

## 3. Unwind data: a genuine gap

`depends.exe` carries a 55,560-byte `.pdata`. The record layout, recovered by
fitting candidate strides and checking the fields land in `.text`:

```c
typedef struct {                 /* 40 bytes */
    ULONGLONG BeginAddress;
    ULONGLONG EndAddress;
    ULONGLONG ExceptionHandler;
    ULONGLONG HandlerData;
    ULONGLONG PrologEndAddress;
} ALPHA64_RUNTIME_FUNCTION;
```

1,389 records, filling the section exactly with no remainder; every record
plausible, all ascending, all contiguous, covering 92.7% of `.text`. 399 have
a non-null handler, drawn from 202 distinct handlers — one of which serves
184 functions. Prologue lengths cluster at 0, 3, 4, 5 and 6 instructions.

**This toolchain emits no `.pdata`.** `_CxxFrameHandler` and
`_OtsCSpecificHandler` report and stop rather than corrupt state. An
exception raised while a gcc frame is on the stack cannot be unwound.

In practice `depends.exe` dispatches no exception during a successful run —
the stubs are never reached — but this is the one place where the port is
incomplete rather than merely different.

## 4. `_Ots*`: a contract gcc cannot express

Microsoft's Alpha compiler calls `_Otsstrlen`, `_Otsstrcpy`, `_OtsMove` and
friends for string and block work, and assumes they preserve every register
not used to pass an argument. `depends.exe` relies on it directly:

```
mov  a0, t0            ; keep the string in t0
bsr  ra, _Otsstrlen
addq t0, v0, a0        ; t0 still live
```

A C implementation compiled by gcc may clobber `t0`. These are therefore
implemented as native gates that write `$0` and nothing else, for the same
reason `__divq` and friends are native.

## 5. What this does and does not prove

**Exercised, by a genuine Microsoft AXP64 binary calling this toolchain's
output and being called back by it:** argument passing in both directions
(including varargs through `wsprintfA`), return values, callee-saved register
discipline across thousands of calls, indirect dispatch through C++ vtables,
MFC message maps, `OnChildNotify`, `DrawItem`, and the window procedure —
enough that Dependency Walker renders its full window, populates its module
tree and import/export lists, and correctly reports *"Modules with different
CPU types were found"* with `Alpha 64` against `x86-64`.

**Not exercised by this binary:** `depends.exe` contains six floating-point
memory touches in total and no FP arithmetic, so the FP and MVI translation is
validated against real Alpha hardware semantics by the differential test
harness, not by this application. SEH is untested because it never fires.
Struct-by-value return and the `$f16`–`$f21` varargs spill path are each
exercised by exactly one function.

**A single application is a single data point.** It is a demanding one — MFC
4.2, C++ vtables, message maps, owner-draw — but it is one program, and the
`.pdata` gap is real.
