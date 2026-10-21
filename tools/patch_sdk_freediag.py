#!/usr/bin/env python3
"""Parche idempotente: registra los MmFreePhysicalMemory (los que fallan siempre; los grandes tambien).
Uso: patch_sdk_freediag.py <xboxkrnl_memory.cpp>
"""
import sys
p = sys.argv[1]
s = open(p).read()
if 'FH2_FREEDIAG' in s:
    print('freediag ya parcheado'); sys.exit(0)
a = '''  auto heap = REX_KERNEL_MEMORY()->LookupHeap(base_address);
  heap->Release(base_address);
}'''
assert s.count(a) == 1, s.count(a)
n = '''  auto heap = REX_KERNEL_MEMORY()->LookupHeap(base_address);
  // FH2_FREEDIAG: si la direccion cae en un bloque enorme que expulsamos a la fuerza, el juego libera algo que ya no existe
  // (y esa zona ya es del bloque nuevo): se ignora para no destruir el bloque nuevo.
  {
    std::lock_guard<std::mutex> g_fh2(fh2_huge::mu());
    auto& ev_fh2 = fh2_huge::evicted();
    for (auto it_fh2 = ev_fh2.begin(); it_fh2 != ev_fh2.end(); ++it_fh2) {
      if (base_address >= it_fh2->first && base_address - it_fh2->first < it_fh2->second) {
        REXKRNL_ERROR("[fh2] MmFreePhysicalMemory ignorado: {:#x} cae en el bloque enorme ya expulsado {:#x}", (uint32_t)base_address,
                      it_fh2->first);
        ev_fh2.erase(it_fh2);
        return;
      }
    }
  }
  uint32_t liberado_fh2 = 0;
  bool ok_fh2 = heap->Release(base_address, &liberado_fh2);
  uint32_t inicio_fh2 = base_address;
  if (!ok_fh2) {
    // Como el nucleo real: una direccion DENTRO de la reserva libera la reserva entera.
    uint32_t inicio_reg = base_address;
    uint32_t tam_reg = 0;
    if (heap->QueryBaseAndSize(&inicio_reg, &tam_reg) && tam_reg != 0) {
      inicio_reg += heap->heap_base();
      if (inicio_reg != base_address) {
        inicio_fh2 = inicio_reg;
        ok_fh2 = heap->Release(inicio_reg, &liberado_fh2);
      }
    }
    REXKRNL_ERROR("[fh2] MmFreePhysicalMemory direccion interior: type={:#x} addr={:#x} inicio_reserva={:#x} tam={:#x} -> {}",
                  (uint32_t)type, (uint32_t)base_address, inicio_fh2, tam_reg, ok_fh2 ? "liberada" : "FALLO");
  }
  if (ok_fh2) {
    std::lock_guard<std::mutex> g_fh2(fh2_huge::mu());
    auto& lv_fh2 = fh2_huge::live();
    for (auto it_fh2 = lv_fh2.begin(); it_fh2 != lv_fh2.end(); ++it_fh2) {
      if (it_fh2->first == inicio_fh2) { lv_fh2.erase(it_fh2); break; }
    }
  }
  if (ok_fh2 && inicio_fh2 == base_address && liberado_fh2 >= 0x400000u) {
    REXKRNL_ERROR("[fh2] MmFreePhysicalMemory grande ok: addr={:#x} liberado={:#x}", (uint32_t)base_address, liberado_fh2);
  }
}'''
open(p, 'w').write(s.replace(a, n))
print('freediag parcheado')
