import sys, struct, collections, pefile
pe = pefile.PE(sys.argv[1]); base = pe.OPTIONAL_HEADER.ImageBase
img = pe.get_memory_mapped_image()
sec = {s.Name.rstrip(b'\0').decode(): (s.VirtualAddress, s.Misc_VirtualSize) for s in pe.sections}
pva, pvs = sec['.pdata']; tva, tvs = sec['.text']
pd = img[pva:pva+pvs]
lo, hi = base+tva, base+tva+tvs
recs = [struct.unpack_from('<5Q', pd, k*40) for k in range(pvs//40)]
print("records: %d   (.pdata virtual size %d = %d*40 + %d)" % (len(recs), pvs, pvs//40, pvs%40))
print("fields per record, interpreted as {Begin, End, ExceptionHandler, HandlerData, PrologEnd}:")
nh = sum(1 for r in recs if r[2]); 
print("  non-null ExceptionHandler : %d / %d  (%.1f%%)" % (nh, len(recs), 100.0*nh/len(recs)))
print("  non-null HandlerData      : %d / %d" % (sum(1 for r in recs if r[3]), len(recs)))
ok = sum(1 for r in recs if r[0] <= r[4] <= r[1])
print("  PrologEnd within [Begin,End] : %d / %d" % (ok, len(recs)))
print("  contiguous (End[i] <= Begin[i+1]) : %d / %d" % (
      sum(1 for a,b in zip(recs, recs[1:]) if a[1] <= b[0]), len(recs)-1))
pl = collections.Counter((r[4]-r[0])//4 for r in recs)
print("  prologue length in instructions, most common:",
      ", ".join("%d:%d"%(k,v) for k,v in pl.most_common(8)))
sz = [ (r[1]-r[0]) for r in recs ]
print("  function size: min %d  median %d  max %d bytes" % (min(sz), sorted(sz)[len(sz)//2], max(sz)))
hs = collections.Counter(r[2] for r in recs if r[2])
print("  distinct exception handlers: %d" % len(hs))
for h,c in hs.most_common(5): print("     0x%x used by %d functions" % (h, c))
# coverage vs the bsr target set
words = struct.unpack('<%dI' % (tvs//4), img[tva:tva+(tvs//4)*4])
bt=set()
for i,w in enumerate(words):
    if (w>>26)&0x3f==0x34 and (w>>21)&0x1f==26:
        d=w&0x1fffff; d-= 0x200000 if d&0x100000 else 0
        bt.add(lo+(i+1)*4+d*4)
begins = set(r[0] for r in recs)
print("  bsr targets covered by a .pdata record begin: %d / %d" % (len(bt&begins), len(bt)))
print("  .pdata covers %d bytes of the %d-byte .text (%.1f%%)" % (sum(sz), tvs, 100.0*sum(sz)/tvs))
