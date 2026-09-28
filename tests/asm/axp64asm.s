/* A Windows AXP64 program written entirely in DEC Alpha assembly.
 *
 * It exists to show that this toolchain's input is the architecture, not a
 * C compiler: the instructions below are hand-written Alpha, including three
 * that no portable C would produce -- CMPBGE, ZAPNOT, and PERR from the
 * Motion Video Instruction extension.
 *
 *   mkaxp64.sh -o axp64asm.exe --base 0x400000 --entry entry \
 *       --import "KERNEL32.dll:OutputDebugStringA,ExitProcess" axp64asm.s
 */
	.arch	ev6
	.set	noreorder
	.set	noat

/* The data sections sit further than 32 KB from gp, so a gp-relative
 * address needs the two-instruction form rather than a bare `lda`. */
	.macro	gpaddr	reg, sym
	ldah	\reg, \sym($29)	!gprelhigh
	lda	\reg, \sym(\reg)	!gprellow
	.endm

/* ------------------------------------------------------------------ data */
	.section .rodata
	.align 3
banner:	.asciz	"AXP64, hand-written Alpha assembly\n"
l_len:	.asciz	"cmpbge strlen  = 0x"
l_perr:	.asciz	"perr   (MVI)   = 0x"
l_zap:	.asciz	"zapnot         = 0x"
l_min:	.asciz	"minub8 (MVI)   = 0x"
l_ok:	.asciz	"all four match the expected values\n"
l_bad:	.asciz	"MISMATCH\n"
nl:	.asciz	"\n"

	.align 3
subject:.asciz	"Hello, AXP64 world"	/* 18 bytes, so strlen is 0x12 */

	.align 3
pa:	.quad	0x1020304050607080	/* operands for the MVI instructions */
pb:	.quad	0x1121314151617181

	.section .bss
	.align 3
buf:	.space	32

/* ------------------------------------------------------------------ code */
	.text

/* puts($16 = zero-terminated string) */
	.globl	puts_
	.ent	puts_
puts_:
	lda	$30, -16($30)
	stq	$26, 0($30)
	stq	$29, 8($30)		/* gp is CALLER-saved: a call through the
				 * GOT into another module may return with
				 * any value in $29, so save it across. */
	ldq	$27, OutputDebugStringA($29)	!literal!1
	jsr	$26, ($27), 0			!lituse_jsr!1
	ldq	$29, 8($30)
	ldq	$26, 0($30)
	lda	$30, 16($30)
	ret	$31, ($26), 1
	.end	puts_

/* puthex($16 = value) -- 16 hex digits into buf, then print */
	.globl	puthex
	.ent	puthex
puthex:
	lda	$30, -16($30)
	stq	$26, 0($30)
	gpaddr	$1, buf
	lda	$2, 60			/* shift count, high nibble first */
	lda	$3, 0			/* byte index */
1:
	srl	$16, $2, $4
	and	$4, 15, $4
	cmplt	$4, 10, $5
	beq	$5, 2f
	addq	$4, 48, $4		/* '0' */
	br	$31, 3f
2:	addq	$4, 87, $4		/* 'a' - 10 */
3:	addq	$1, $3, $5
	stb	$4, 0($5)
	addq	$3, 1, $3
	subq	$2, 4, $2
	bge	$2, 1b
	addq	$1, $3, $5
	lda	$4, 10			/* '\n' */
	stb	$4, 0($5)
	addq	$1, $3, $5
	stb	$31, 1($5)		/* terminate */
	bis	$31, $1, $16
	bsr	$26, puts_
	ldq	$26, 0($30)
	lda	$30, 16($30)
	ret	$31, ($26), 1
	.end	puthex

	.globl	entry
	.ent	entry
entry:
	ldgp	$29, 0($27)		/* SysV prologue: gp from the procedure value */
	lda	$30, -64($30)
	stq	$26, 0($30)
	stq	$9, 8($30)
	stq	$10, 16($30)
	stq	$11, 24($30)
	stq	$12, 32($30)
	stq	$13, 40($30)
	stq	$14, 48($30)

	gpaddr	$16, banner
	bsr	$26, puts_

/* ---- 1. strlen the Alpha way: CMPBGE against zero, eight bytes at a time */
	gpaddr	$1, subject
	bis	$31, $1, $2		/* keep the start */
1:	ldq	$3, 0($1)
	cmpbge	$31, $3, $4		/* bit i set where byte i of $3 is zero */
	bne	$4, 2f
	lda	$1, 8($1)
	br	$31, 1b
2:	subq	$1, $2, $9		/* whole quadwords consumed */
	/* the low set bit of $4 is the index of the terminator in this word */
	negq	$4, $5
	and	$4, $5, $5		/* isolate the lowest set bit */
	/* turn the one-hot value into its bit index by a small compare chain */
	lda	$6, 0
3:	blbs	$5, 4f
	srl	$5, 1, $5
	addq	$6, 1, $6
	br	$31, 3b
4:	addq	$9, $6, $9		/* $9 = strlen */

	gpaddr	$16, l_len
	bsr	$26, puts_
	bis	$31, $9, $16
	bsr	$26, puthex

/* ---- 2. PERR: sum of absolute differences of the eight byte lanes ------ */
	/* $13 and $14 are callee-saved, so the operands survive the puts_
	 * and puthex calls below.  $1-$8 would not. */
	gpaddr	$1, pa
	ldq	$13, 0($1)
	gpaddr	$1, pb
	ldq	$14, 0($1)
	perr	$13, $14, $10		/* MVI: 8 x |a_i - b_i|, summed */

	gpaddr	$16, l_perr
	bsr	$26, puts_
	bis	$31, $10, $16
	bsr	$26, puthex

/* ---- 3. ZAPNOT: keep the byte lanes named by a mask ------------------- */
	zapnot	$13, 0x0f, $11		/* keep the low four bytes */

	gpaddr	$16, l_zap
	bsr	$26, puts_
	bis	$31, $11, $16
	bsr	$26, puthex

/* ---- 4. MINUB8: per-lane unsigned byte minimum ------------------------ */
	minub8	$13, $14, $12		/* MVI */

	gpaddr	$16, l_min
	bsr	$26, puts_
	bis	$31, $12, $16
	bsr	$26, puthex

/* ---- check ------------------------------------------------------------ */
	lda	$1, 18
	cmpeq	$9, $1, $5
	beq	$5, 9f
	lda	$1, 8
	cmpeq	$10, $1, $5		/* 8 lanes, |a-b| = 1 each */
	beq	$5, 9f
	ldah	$1, 0x5060($31)
	lda	$1, 0x7080($1)
	zapnot	$1, 0x0f, $1
	cmpeq	$11, $1, $5
	beq	$5, 9f
	cmpeq	$12, $13, $5		/* every lane of pa is the smaller one,
	beq	$5, 9f			 * so minub8(pa,pb) == pa */
	gpaddr	$16, l_ok
	bsr	$26, puts_
	lda	$17, 0
	br	$31, 10f
9:	gpaddr	$16, l_bad
	bsr	$26, puts_
	lda	$17, 1
10:
	bis	$31, $17, $16
	ldq	$27, ExitProcess($29)		!literal!2
	jsr	$26, ($27), 0			!lituse_jsr!2

	/* ExitProcess does not come back on real Windows, but the guest
	 * KERNEL32 here tail-calls its host gate, so control can land on the
	 * next instruction.  End the function properly rather than running
	 * off into whatever follows. */
	ldq	$14, 48($30)
	ldq	$13, 40($30)
	ldq	$12, 32($30)
	ldq	$11, 24($30)
	ldq	$10, 16($30)
	ldq	$9, 8($30)
	ldq	$26, 0($30)
	lda	$30, 64($30)
	ret	$31, ($26), 1
	.end	entry
