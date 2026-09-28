#!/usr/bin/env python3
"""Statically measure the Alpha calling convention used by a PE image.

Emits only derived statistics -- never raw disassembly.
"""
import sys, struct, collections
import pefile

REGN = {0:'v0',26:'ra',27:'pv/t12',28:'at',29:'gp',30:'sp',31:'zero'}
for i in range(1,9):   REGN.setdefault(i,  't%d'%(i-1))
for i in range(9,15):  REGN.setdefault(i,  's%d'%(i-9))
REGN.setdefault(15,'fp/s6')
for i in range(16,22): REGN.setdefault(i,  'a%d'%(i-16))
for i in range(22,26): REGN.setdefault(i,  't%d'%(i-14))
def rn(r): return '$%d(%s)' % (r, REGN.get(r,'?'))

OP_LDA, OP_LDAH, OP_LDL, OP_LDQ, OP_STQ, OP_STL = 0x08,0x09,0x28,0x29,0x2d,0x2c
OP_JSR, OP_BR, OP_BSR = 0x1a, 0x30, 0x34

class Img:
    def __init__(self, path):
        pe = pefile.PE(path)
        self.pe = pe
        self.base = pe.OPTIONAL_HEADER.ImageBase
        self.mach = pe.FILE_HEADER.Machine
        self.img = pe.get_memory_mapped_image()
        self.sec = {}
        for s in pe.sections:
            n = s.Name.rstrip(b'\0').decode(errors='replace')
            self.sec[n] = (s.VirtualAddress, s.Misc_VirtualSize, s.SizeOfRawData)
    def data(self, name):
        va, vs, rs = self.sec[name]
        return va + self.base, self.img[va:va+vs]

def decode(w):
    return (w >> 26) & 0x3f, (w >> 21) & 0x1f, (w >> 16) & 0x1f, w & 0xffff

def signed16(x): return x - 0x10000 if x & 0x8000 else x

def main(path):
    im = Img(path)
    print("image        : %s" % path)
    print("machine      : 0x%04x   imagebase 0x%x" % (im.mach, im.base))
    print("sections     : %s" % ", ".join(im.sec))
    tva, text = im.data('.text')
    n = len(text)//4
    words = struct.unpack('<%dI' % n, text[:n*4])
    print("text words   : %d  (%d bytes @ 0x%x)" % (n, n*4, tva))
    print()

    # ---- 1. indirect calls: jsr ra,(rB) --------------------------------
    jsr_by_rb = collections.Counter()
    jmp_by_rb = collections.Counter()
    bsr_targets = set()
    jsr_sites = []
    for i, w in enumerate(words):
        op, ra, rb, rest = decode(w)
        if op == OP_JSR:
            func = (rest >> 14) & 3
            if func == 1 and ra == 26:            # JSR ra,(rb)
                jsr_by_rb[rb] += 1
                jsr_sites.append(i)
            elif func == 0 and ra == 31:          # JMP zero,(rb)  = tail/indirect jump
                jmp_by_rb[rb] += 1
        elif op == OP_BSR and ra == 26:
            d = rest | (((w >> 16) & 0x1f) << 16)
            d = (w & 0x1fffff)
            if d & 0x100000: d -= 0x200000
            bsr_targets.add(tva + (i+1)*4 + d*4)
    tot = sum(jsr_by_rb.values())
    print("== 1. indirect calls  `jsr ra,(rX)` ==")
    print("total indirect call sites: %d" % tot)
    for r, c in jsr_by_rb.most_common(10):
        print("   %-14s %6d   %5.1f%%" % (rn(r), c, 100.0*c/max(tot,1)))
    print("   [SysV/OSF-1 requires X == $27 (pv) so the callee can ldgp]")
    print("   pv-register share: %.1f%%" % (100.0*jsr_by_rb.get(27,0)/max(tot,1)))
    print()
    print("direct calls `bsr ra,target`: %d sites, %d distinct targets"
          % (sum(1 for i,w in enumerate(words) if (w>>26)&0x3f==OP_BSR and (w>>21)&0x1f==26),
             len(bsr_targets)))
    print()

    # ---- 2. prologue idiom at bsr targets ------------------------------
    print("== 2. function-entry idiom (sampled at %d bsr targets) ==" % len(bsr_targets))
    ldgp = 0; other = collections.Counter()
    for t in sorted(bsr_targets):
        idx = (t - tva)//4
        if idx < 0 or idx+1 >= n: continue
        w0, w1 = words[idx], words[idx+1]
        op0, ra0, rb0, _ = decode(w0)
        op1, ra1, rb1, _ = decode(w1)
        # ldgp = ldah $29,hi($27) ; lda $29,lo($29)
        if op0 == OP_LDAH and ra0 == 29 and rb0 == 27 and op1 == OP_LDA and ra1 == 29:
            ldgp += 1
        else:
            other[op0] += 1
    OPNAME = {0x08:'lda',0x09:'ldah',0x28:'ldl',0x29:'ldq',0x2c:'stl',0x2d:'stq',
              0x10:'<int arith>',0x11:'<int logic>',0x12:'<int shift>',0x13:'<int mul>',
              0x26:'sts',0x27:'stt',0x22:'lds',0x23:'ldt',0x30:'br',0x34:'bsr',0x1a:'jsr/jmp/ret'}
    print("   entries beginning with the ldgp idiom (ldah gp,($27); lda gp): %d" % ldgp)
    print("   entries beginning with something else                       : %d" % sum(other.values()))
    for op, c in other.most_common(8):
        print("      first opcode 0x%02x %-14s %5d" % (op, OPNAME.get(op,''), c))
    print()

    # ---- 3. frame sizes  lda $30,-N($30) -------------------------------
    print("== 3. frame allocation  `lda sp,-N(sp)` ==")
    frames = collections.Counter()
    for w in words:
        op, ra, rb, d = decode(w)
        if op == OP_LDA and ra == 30 and rb == 30:
            v = signed16(d)
            if v < 0: frames[-v] += 1
    tf = sum(frames.values())
    print("   %d frame-allocating instructions" % tf)
    small = sum(c for s,c in frames.items() if s < 48)
    print("   frames < 48 bytes (too small for a 6-quadword argument home area): %d  (%.1f%%)"
          % (small, 100.0*small/max(tf,1)))
    print("   most common sizes:", ", ".join("%d:%d" % (s,c) for s,c in frames.most_common(8)))
    print()

    # ---- 4. gp reload after calls --------------------------------------
    print("== 4. gp ($29) handling ==")
    gp_written = collections.Counter()
    for w in words:
        op, ra, rb, d = decode(w)
        if op in (OP_LDA, OP_LDAH, OP_LDQ, OP_LDL) and ra == 29:
            gp_written[op] += 1
    print("   instructions writing $29:", ", ".join("%s:%d" % (OPNAME.get(o,hex(o)),c)
                                                    for o,c in gp_written.most_common()) or "none")
    # ldq gp,N(sp) right after a call is the SysV "restore gp after call" idiom
    restore = 0
    for i in jsr_sites:
        if i+1 < n:
            op, ra, rb, d = decode(words[i+1])
            if op == OP_LDQ and ra == 29 and rb == 30:
                restore += 1
    print("   indirect calls followed by `ldq gp,N(sp)` (SysV restore idiom): %d / %d"
          % (restore, tot))
    print()

    # ---- 5. .pdata ------------------------------------------------------
    if '.pdata' in im.sec:
        pva, pd = im.data('.pdata')
        print("== 5. .pdata ==")
        print("   virtual size %d bytes @ 0x%x" % (len(pd), pva))
        lo = im.base + im.sec['.text'][0]
        hi = lo + im.sec['.text'][1]
        for stride, fmt, label in ((20,'<5I','5 x DWORD  (Alpha32 RUNTIME_FUNCTION)'),
                                   (40,'<5Q','5 x QWORD  (Alpha64 RUNTIME_FUNCTION)'),
                                   (32,'<4Q','4 x QWORD'),
                                   (24,'<3Q','3 x QWORD')):
            cnt = len(pd)//stride
            if cnt < 4: continue
            ok = 0; mono = 0; prev = 0
            for k in range(cnt):
                f = struct.unpack_from(fmt, pd, k*stride)
                b, e = f[0], f[1]
                if lo <= b < hi and lo < e <= hi and b < e:
                    ok += 1
                    if b >= prev: mono += 1
                    prev = b
            print("   stride %2d (%s): %d records, %d plausible (%.0f%%), %d ascending"
                  % (stride, label, cnt, ok, 100.0*ok/cnt, mono))
        print()

if __name__ == '__main__':
    main(sys.argv[1])
