#!/usr/bin/env python3
"""Parche idempotente: la trampa de 'llamada a funcion invalida' ya no mata el juego.
Se ignora la llamada (r3=0), se limpia el hueco de retorno de la pila (si r3 apunta a la pila del llamador, se pone a 0
su primera palabra: asi un puntero inteligente devuelto queda nulo y no basura) y se registra cada pareja distinta
(destino, lr) una sola vez (hasta 300), con contadores.
Uso: patch_sdk_trapdiag.py <function_dispatcher.cpp>
"""
import sys
p = sys.argv[1]
s = open(p).read()
if 'FH2_TRAPDIAG' in s:
    print('trapdiag ya parcheado'); sys.exit(0)
sig = 'static void InvalidFunctionTrap(PPCContext& ctx, uint8_t* /*base*/) {'
assert s.count(sig) == 1, s.count(sig)
a = '''  REX_FATAL("Call to invalid or unregistered function at guest address 0x{:08X}",
            ctx.last_indirect_target);'''
assert s.count(a) == 1, s.count(a)
n = '''  // FH2_TRAPDIAG
  {
    static std::atomic<uint64_t> total_fh2{0};
    static std::mutex mu_fh2;
    static std::set<uint64_t> vistos_fh2;
    const uint64_t cuenta_fh2 = total_fh2.fetch_add(1) + 1;
    const uint64_t clave_fh2 = ((uint64_t)(uint32_t)ctx.lr << 32) | (uint64_t)ctx.last_indirect_target;
    bool nuevo_fh2 = false;
    {
      std::lock_guard<std::mutex> g_fh2(mu_fh2);
      if (vistos_fh2.size() < 300) nuevo_fh2 = vistos_fh2.insert(clave_fh2).second;
    }
    if (nuevo_fh2) {
      REXSYS_WARN("[fh2] llamada invalida ignorada #{} (destino=0x{:08X} lr=0x{:08X} r3=0x{:08X} r4=0x{:08X} r5=0x{:08X} r1=0x{:08X})",
                  cuenta_fh2, ctx.last_indirect_target, (uint32_t)ctx.lr, (uint32_t)ctx.r3.u32, (uint32_t)ctx.r4.u32,
                  (uint32_t)ctx.r5.u32, (uint32_t)ctx.r1.u32);
    }
    if (cuenta_fh2 == 1000 || cuenta_fh2 == 100000 || cuenta_fh2 == 1000000) {
      REXSYS_WARN("[fh2] llamadas invalidas ignoradas hasta ahora: {}", cuenta_fh2);
    }
    if (cuenta_fh2 > 5000000) {
      REX_FATAL("Demasiadas llamadas invalidas ({}), ultimo destino 0x{:08X} lr=0x{:08X}", cuenta_fh2,
                ctx.last_indirect_target, (uint32_t)ctx.lr);
    }
    // Hueco de retorno en la pila del llamador (r3 = r1+N): dejarlo nulo.
    const uint32_t r1_fh2 = ctx.r1.u32, r3_fh2 = ctx.r3.u32;
    if (r3_fh2 >= r1_fh2 && (r3_fh2 - r1_fh2) < 0x1000 && (r3_fh2 & 3) == 0) {
      *reinterpret_cast<volatile uint32_t*>(base + r3_fh2) = 0;
    }
    ctx.r3.u64 = 0;
    return;
  }'''
s = s.replace(sig, 'static void InvalidFunctionTrap(PPCContext& ctx, uint8_t* base) {')
s = s.replace(a, n)
for inc in ('#include <atomic>', '#include <mutex>', '#include <set>'):
    if inc not in s:
        s = s.replace('#include <rex/assert.h>', inc + '\n#include <rex/assert.h>', 1)
open(p, 'w').write(s)
print('trapdiag parcheado')
