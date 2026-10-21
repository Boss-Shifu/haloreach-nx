#!/usr/bin/env python3
"""Parche idempotente (va despues de patch_sdk_nullpage.py): operaciones atomicas del invitado (lwarx/stwcx. -> ldxr/stxr
de AArch64) sobre la pagina nula (0..64 KB). El decodificador normal no las reconoce y el juego moria al hacer
Release() de un objeto nulo (leia 0x4). Aqui: LDXR/LDAXR devuelve 0 y STXR/STLXR 'tiene exito' sin escribir.
Uso: patch_sdk_nullatomic.py <exception_handler_switch.cpp>"""
import sys
p = sys.argv[1]
s = open(p).read()
if 'FH2_NULLATOMIC' in s:
    print('nullatomic ya parcheado'); sys.exit(0)
anchor = '        if (RexDecodeAccess(ctx, insn_n, &acc_n)) {'
assert s.count(anchor) == 1, s.count(anchor)
new = '''        // FH2_NULLATOMIC: exclusivos sobre la pagina nula
        if ((insn_n & 0x3F600000u) == 0x08400000u) {          // LDXR / LDAXR (y B/H)
          RexGprWrite(ctx, insn_n & 0x1F, 0);
          ctx->pc.x += 4;
          RexResumeFromException(ctx);
        }
        if ((insn_n & 0x3F600000u) == 0x08000000u) {          // STXR / STLXR (y B/H)
          RexGprWrite(ctx, (insn_n >> 16) & 0x1F, 0);        // estado 0 = exito
          ctx->pc.x += 4;
          RexResumeFromException(ctx);
        }
''' + anchor
open(p, 'w').write(s.replace(anchor, new))
print('nullatomic parcheado')
