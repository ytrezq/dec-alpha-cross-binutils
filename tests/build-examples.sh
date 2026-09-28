#!/bin/sh
# Build every example in tests/ into prebuilt/examples/.
#   tests/build-examples.sh
set -e
cd "$(dirname "$0")/.."
MK=./mkaxp64.sh
OUT=prebuilt/examples
mkdir -p "$OUT"

# 1. hand-written DEC Alpha assembly, self-checking
$MK -o "$OUT/axp64asm.exe" --base 0x400000 --entry entry \
    --import "KERNEL32.dll:OutputDebugStringA,ExitProcess" \
    tests/asm/axp64asm.s >/dev/null
echo "axp64asm.exe"

# 2. a C Win32 GUI program
$MK -o "$OUT/hello-gui.exe" --base 0x400000 --entry entry \
    --import "USER32.dll:RegisterClassA,CreateWindowExA,ShowWindow,UpdateWindow,DestroyWindow,DefWindowProcA,GetMessageA,TranslateMessage,DispatchMessageA,PostQuitMessage,BeginPaint,EndPaint,GetClientRect,LoadCursorA,SetTimer,FillRect" \
    --import "GDI32.dll:CreateSolidBrush,DeleteObject,SetBkMode,SetTextColor,TextOutA,Ellipse,MoveToEx,LineTo" \
    --import "KERNEL32.dll:OutputDebugStringA,ExitProcess" \
    tests/hello-gui.c >/dev/null
echo "hello-gui.exe"

# 3. the procedure-value experiment from ABI.md, both ways
$MK -o "$OUT/LIB.dll"   --dll --base 0x60000000 --entry DllMain \
    --import "winhost:__mfc_trace" --export probe tests/pv/lib.c >/dev/null
$MK -o "$OUT/LIBNT.dll" --dll --base 0x60100000 --entry DllMain --no-pv-thunk \
    --import "winhost:__mfc_trace" --export probe tests/pv/lib.c >/dev/null
sed 's/probe/probe/' tests/pv/caller.c > /tmp/pvcaller.c
$MK -o "$OUT/call_LIB.exe"   --base 0x400000 --entry entry \
    --import "LIB.dll:probe"   --import "winhost:__mfc_trace" \
    --import "KERNEL32.dll:ExitProcess" /tmp/pvcaller.c >/dev/null
$MK -o "$OUT/call_LIBNT.exe" --base 0x400000 --entry entry \
    --import "LIBNT.dll:probe" --import "winhost:__mfc_trace" \
    --import "KERNEL32.dll:ExitProcess" /tmp/pvcaller.c >/dev/null
rm -f /tmp/pvcaller.c
echo "LIB.dll LIBNT.dll call_LIB.exe call_LIBNT.exe"

for f in "$OUT"/*; do
  python3 - "$f" <<'PY'
import sys, pefile
pe = pefile.PE(sys.argv[1])
print("  %-16s machine 0x%04x  base 0x%x" % (
      sys.argv[1].split('/')[-1], pe.FILE_HEADER.Machine, pe.OPTIONAL_HEADER.ImageBase))
PY
done
