#!/usr/bin/env python3
"""Parche idempotente: modo TOLERANTE para accesos del invitado a memoria no mapeada (opcion tolerante=1).

Cuando un acceso a la ventana del invitado no se puede resolver por ninguna via y iba a terminar en el cierre fatal,
con tolerante=1 se emula: las lecturas devuelven 0 y las escrituras se descartan, se avanza el PC y se sigue. Se anotan
los primeros accesos en rex_crash.log con el titulo "acceso tolerado" (direccion, pc, instruccion) y un contador.
Es una red de seguridad para juegos nuevos: puede evitar que un hilo muera, pero NO garantiza que el juego funcione.
La opcion se lee de <logs/rex>/opciones.ini (clave tolerante=0/1) o de sdmc:/switch/FH2/opciones.ini.
Uso: patch_sdk_tolerante.py <exception_handler_switch.cpp> [valor_por_defecto 0|1]
"""
import sys
p = sys.argv[1]
defecto = sys.argv[2] if len(sys.argv) > 2 else '0'
assert defecto in ('0', '1')
s = open(p).read()
if 'FH2_TOLERANTE' in s:
    print('tolerante ya parcheado'); sys.exit(0)

ai = '#include <cstring>\n'
assert s.count(ai) == 1, s.count(ai)
s = s.replace(ai, ai + '#include <cstdlib>\n#include <string>\n')
a1 = 'namespace rex::arch {\n\nstatic_assert(sizeof(vec128_t)'
assert s.count(a1) == 1, s.count(a1)
n1 = '''extern "C" const char* RexSwitchLogDir(void);

// FH2_TOLERANTE: lee la clave tolerante de opciones.ini (una vez).
static int Fh2Tolerante() {
  static int valor = -1;
  if (valor >= 0) return valor;
  valor = %s;
  const char* dir = RexSwitchLogDir();
  const std::string rutas[2] = {std::string(dir ? dir : "") + "opciones.ini", "sdmc:/switch/FH2/opciones.ini"};
  for (const auto& r : rutas) {
    FILE* f = std::fopen(r.c_str(), "r");
    if (!f) continue;
    char l[128];
    while (std::fgets(l, sizeof(l), f)) {
      if (std::strncmp(l, "tolerante=", 10) == 0) valor = std::atoi(l + 10) != 0 ? 1 : 0;
    }
    std::fclose(f);
    break;
  }
  return valor;
}

''' % defecto + a1
s = s.replace(a1, n1)

a2 = '''  // --- 4. fatal --------------------------------------------------------------'''
assert s.count(a2) == 1, s.count(a2)
n2 = '''  // FH2_TOLERANTE: red de seguridad (ver patch_sdk_tolerante.py)
  if (data_abort && in_window && Fh2Tolerante()) {
    alignas(16) static uint8_t ceros_t[64];
    alignas(16) static uint8_t sumidero_t[64];
    static volatile uint32_t contador_t = 0;
    RexAccess acc_t;
    const uint32_t insn_t = *reinterpret_cast<const uint32_t*>(ctx->pc.x);
    if (RexDecodeAccess(ctx, insn_t, &acc_t)) {
      const size_t total_t = static_cast<size_t>(acc_t.bytes) * (acc_t.rt2 != 0xFF ? 2 : 1);
      if (total_t <= 64) {
        const uint32_t n_t = __atomic_add_fetch(&contador_t, 1, __ATOMIC_RELAXED);
        if (n_t <= 40) {
          RexSwitchCrashLog(is_write ? "acceso tolerado (escritura descartada)" : "acceso tolerado (lectura = 0)", ctx,
                            ctx->sp.x, pc);
        }
        std::memset(ceros_t, 0, sizeof(ceros_t));
        RexEmulateAccess(ctx, &acc_t, is_write ? static_cast<void*>(sumidero_t) : static_cast<void*>(ceros_t));
        ctx->pc.x += 4;
        RexResumeFromException(ctx);
      }
    }
  }

''' + a2
s = s.replace(a2, n2)
open(p, 'w').write(s)
print('tolerante parcheado (defecto %s)' % defecto)
