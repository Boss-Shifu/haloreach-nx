#!/usr/bin/env python3
"""Parche idempotente: registra (nivel error, siempre visible) las reservas de memoria grandes (>= 4 MB) del invitado.
Sirve para saber quien se come los 512 MB fisicos antes de que falle la carga de la pista.
Uso: patch_sdk_allocdiag.py <xboxkrnl_memory.cpp>
"""
import sys
p = sys.argv[1]
s = open(p).read()
if 'FH2_ALLOCDIAG' in s:
    print('allocdiag ya parcheado'); sys.exit(0)
a1 = '''      input_base, input_size, (uint32_t)alloc_type, (uint32_t)protect_bits, (uint32_t)debug_memory);
'''
assert s.count(a1) == 1, s.count(a1)
n1 = '''  if (input_size >= 0x400000u) {  // FH2_ALLOCDIAG
    REXKRNL_ERROR("[fh2] NtAllocateVirtualMemory grande: base={:#x} size={:#x} ({} MB) type={:#x} protect={:#x}",
                  input_base, input_size, input_size >> 20, (uint32_t)alloc_type, (uint32_t)protect_bits);
  }

'''
s = s.replace(a1, a1 + n1)
a2 = '''  // Check protection bits.
  if (!(protect_bits & (X_PAGE_READONLY | X_PAGE_READWRITE))) {
    REXKRNL_ERROR("MmAllocatePhysicalMemoryEx: bad protection bits");'''
assert s.count(a2) == 1, s.count(a2)
n2 = '''  if (region_size >= 0x400000u) {  // FH2_ALLOCDIAG
    REXKRNL_ERROR("[fh2] MmAllocatePhysicalMemoryEx grande: size={:#x} ({} MB) protect={:#x} align={:#x}",
                  (uint32_t)region_size, (uint32_t)region_size >> 20, (uint32_t)protect_bits, (uint32_t)alignment);
  }

''' + a2
s = s.replace(a2, n2)
a3 = '''  if (!heap->AllocRange(heap_min_addr, heap_max_addr, adjusted_size, adjusted_alignment,
                        allocation_type, protect, top_down, &base_address)) {
    // Failed - assume no memory available.
    return 0;
  }'''
assert s.count(a3) == 1, s.count(a3)
n3 = '''  // FH2_ALLOCRETRY: las reservas enormes (>= 128 MB) van desde ABAJO para no partir la RAM libre.
  const bool enorme_fh2 = adjusted_size >= 0x8000000u;
  const bool td_fh2 = enorme_fh2 ? false : top_down;
  bool virtual_fh2 = false;
  bool ok_fh2 = heap->AllocRange(heap_min_addr, heap_max_addr, adjusted_size, adjusted_alignment,
                                 allocation_type, protect, td_fh2, &base_address);
  if (!ok_fh2 && adjusted_size >= 0x2000000u) {
    // Reserva grande sin sitio: otro hilo puede estar liberando la anterior. Se reintenta hasta ~30 s.
    // Si es enorme y a los 3 s sigue sin sitio, se libera a la fuerza el bloque enorme anterior (el juego
    // reinicia su reserva de medios y la vieja ya no se usa).
    const int espera_fh2 = fh2_opt("espera_reserva", 45);  // s antes de forzar
    const bool hv_fh2 = fh2_opt("heap_virtual", 1) != 0;
    for (int i = 0; i < espera_fh2 * 10 + 450 && !ok_fh2; ++i) {
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
      ok_fh2 = heap->AllocRange(heap_min_addr, heap_max_addr, adjusted_size, adjusted_alignment,
                                allocation_type, protect, td_fh2, &base_address);
      if (!ok_fh2 && enorme_fh2 && hv_fh2 && i == 10) {
        // A 1 s sigue sin sitio: la reserva enorme (medios) no necesita ser fisica; se toma del heap virtual de
        // 64 KB (0x40000000+), asi conviven el bloque viejo y el nuevo hasta que el juego libere el viejo.
        auto* vheap_fh2 = REX_KERNEL_MEMORY()->LookupHeapByType(false, 64 * 1024);
        uint32_t vb_fh2 = 0;
        if (vheap_fh2 && vheap_fh2->Alloc(adjusted_size, 0x10000, allocation_type, protect, false, &vb_fh2)) {
          base_address = vb_fh2;
          ok_fh2 = true;
          virtual_fh2 = true;
          REXKRNL_ERROR("[fh2] reserva enorme de {} MB sin sitio fisico: se toma del heap virtual en {:#x}", adjusted_size >> 20, vb_fh2);
        }
      }
      if (!ok_fh2 && enorme_fh2 && i == espera_fh2 * 10) {
        std::pair<uint32_t, uint32_t> viejo_fh2{0, 0};
        {
          std::lock_guard<std::mutex> g_fh2(fh2_huge::mu());
          if (!fh2_huge::live().empty()) {
            viejo_fh2 = fh2_huge::live().front();
            fh2_huge::live().erase(fh2_huge::live().begin());
            fh2_huge::evicted().push_back(viejo_fh2);
          }
        }
        if (viejo_fh2.second != 0) {
          uint32_t lib_fh2 = 0;
          bool r_fh2 = heap->Release(viejo_fh2.first, &lib_fh2);
          REXKRNL_ERROR("[fh2] reserva enorme sin sitio: se libera a la fuerza el bloque anterior {:#x} ({} MB): {}",
                        viejo_fh2.first, viejo_fh2.second >> 20, r_fh2 ? "liberado" : "FALLO");
        }
      }
    }
    REXKRNL_ERROR("[fh2] MmAllocatePhysicalMemoryEx reintento de {} MB: {}", adjusted_size >> 20, ok_fh2 ? "ok" : "FALLO");
  }
  if (ok_fh2 && enorme_fh2 && !virtual_fh2) {
    std::lock_guard<std::mutex> g_fh2(fh2_huge::mu());
    fh2_huge::live().push_back({base_address, adjusted_size});
    REXKRNL_ERROR("[fh2] reserva enorme ok: {:#x} ({} MB), bloques enormes vivos: {}", base_address, adjusted_size >> 20,
                  fh2_huge::live().size());
  }
  if (!ok_fh2) {
    // Failed - assume no memory available.
    return 0;
  }'''
s = s.replace(a3, n3)
if 'namespace fh2_huge' not in s:
    hdr = '''#include <chrono>
#include <cstdint>
#include <mutex>
#include <thread>
#include <utility>
#include <vector>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

extern "C" const char* RexSwitchLogDir(void);
static int fh2_opt(const char* clave, int def) {  // FH2_OPT: lee <logs/rex>/opciones.ini (clave=valor)
  std::string ruta = std::string(RexSwitchLogDir()) + "opciones.ini";
  FILE* f = std::fopen(ruta.c_str(), "r");
  if (!f) return def;
  char linea[256];
  int val = def;
  const size_t n = std::strlen(clave);
  while (std::fgets(linea, sizeof(linea), f)) {
    if (std::strncmp(linea, clave, n) == 0 && linea[n] == '=') val = std::atoi(linea + n + 1);
  }
  std::fclose(f);
  return val;
}
namespace fh2_huge {  // FH2_HUGE: bloques fisicos enormes vivos / expulsados a la fuerza
inline std::mutex& mu() { static std::mutex m; return m; }
inline std::vector<std::pair<uint32_t, uint32_t>>& live() { static std::vector<std::pair<uint32_t, uint32_t>> v; return v; }
inline std::vector<std::pair<uint32_t, uint32_t>>& evicted() { static std::vector<std::pair<uint32_t, uint32_t>> v; return v; }
}  // namespace fh2_huge
'''
    s = hdr + s
open(p, 'w').write(s)
print('allocdiag parcheado')
