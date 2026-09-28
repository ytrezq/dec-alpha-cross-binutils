/* A caller in the shape MSVC AXP64 code takes: the target lands in $0 and the
 * call is `jsr ra,($0)` with $27 (pv) left holding an unrelated temporary. */
typedef unsigned long long u64;
extern u64 probe(u64);
extern void __mfc_trace(u64,u64,u64,u64,u64,u64,u64,u64);
extern void ExitProcess(unsigned);

static u64 call_via_v0(u64 target, u64 arg, u64 junk_pv)
{
    register u64 t  __asm__("$0")  = target;
    register u64 a0 __asm__("$16") = arg;
    register u64 pv __asm__("$27") = junk_pv;
    __asm__ __volatile__("jsr $26, ($0)"
        : "+r"(t) : "r"(a0), "r"(pv)
        : "$26","$1","$2","$3","$4","$5","$6","$7","$8",
          "$22","$23","$24","$25","$28","memory");
    return t;
}
void entry(void)
{
    u64 target = (u64)(unsigned long)&probe;   /* what the IAT slot holds */
    __mfc_trace(0xAAAA, target, 0,0,0,0,0,0);
    /* 1. the SysV way: gcc sets $27 = target itself */
    __mfc_trace(0x1111, probe(0), 0,0,0,0,0,0);
    /* 2. the MSVC way: $27 holds a stale pointer into the caller's image */
    __mfc_trace(0x2222, call_via_v0(target, 0, 0x400318ULL), 0,0,0,0,0,0);
    ExitProcess(0);
}
