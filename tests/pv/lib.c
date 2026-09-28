/* A DLL in the shape gcc produces: globals reached through gp. */
typedef unsigned long long u64;
extern void __mfc_trace(u64,u64,u64,u64,u64,u64,u64,u64);

u64 g_table[64] = { 0x1122334455667788ULL, 2,3,4,5,6,7,8 };

u64 probe(u64 which)
{
    /* g_table's address comes out of the GOT, i.e. through gp.  The value is
     * only right when gp is right, and gp is only right when $27 held this
     * function's entry address on arrival. */
    u64 v = g_table[which & 63];
    __mfc_trace(0xC0DE, (u64)(unsigned long)g_table, v, 0,0,0,0,0);
    return v;
}
int DllMain(void *h, u64 r, void *x) { (void)h;(void)r;(void)x; return 1; }
