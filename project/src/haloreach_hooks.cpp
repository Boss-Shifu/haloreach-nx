// haloreach_hooks.cpp — Hooks específicos de Halo: Reach (Title ID 4D53085B, build 11860 omaha_release)
// Incluye:
// 1. XMsgStartIORequest (0xFE / 0x00020021 XContentQueryVolumeDeviceType -> X_E_INVALIDARG) para activar el streaming de mapas en cache0:\
// 2. XeKeysConsolePrivateKeySign -> devuelve TRUE con certificado retail Xenia para que el juego firme sus preferencias y cache0XX.map
// 3. XeCryptBnQwNeRsaPubCrypt -> validación RSA portátil en ARM64 para archivos .map y partidas guardadas
// 4. autoport_spin_hint -> convierte esperas activas PowerPC (db16cyc) en yield ARM64 + micro-sleep para liberar los 3 núcleos del Tegra X1 (60 FPS)

#include <rex/hook.h>

#include <chrono>
#include <cstdint>
#include <cstring>
#include <thread>
#include <vector>

#if defined(__SWITCH__)
#include <switch.h>
extern "C" {
// Aumenta la memoria de transferencia de nvdrv a 24 MB (~12,000 texturas NvMap en Halo: Reach sin error 0x235C)
extern uint32_t __nx_nv_transfermem_size;
uint32_t __nx_nv_transfermem_size = 24 * 1024 * 1024;
void RexSwitchRelojesReverseHabilitar(int habilitado);
void RexSwitchApmPedirGpuMhz(int mhz);
void RexSwitchApmAplicar(void);
}
#endif

void HaloReachInitHooks() {
#if defined(__SWITCH__)
  RexSwitchRelojesReverseHabilitar(1);
  if (R_SUCCEEDED(pmshellInitialize())) {
    pmshellBoostApplicationThreadResourceLimit();
    pmshellExit();
  }
  // Solicita el perfil oficial de rendimiento de Horizon OS (apm 0x92220008: 460.8 MHz GPU en portatil / 768 MHz en dock).
  // No fuerza overclock por sys-clk: cada usuario elige su propio overclock al entrar al juego.
  RexSwitchApmPedirGpuMhz(460);
  RexSwitchApmAplicar();
#endif
}

// ============================================================================
// 1. Hook XMsgStartIORequest (Fuerza modo Disco para que Halo: Reach monte cache0:\)
// ============================================================================
// El símbolo __imp__XMsgStartIORequest queda ocupado por este hook, así que el
// paso al SDK no puede hacerse por puntero: se llama directamente a la rutina
// host que usa el export original (XMsgStartIORequest_entry), con los mismos
// registros de entrada (r3..r7) y con unknown = nullptr.
namespace rex::kernel::xam {
struct XMSGSTARTIOREQUEST_UNKNOWNARG;
uint32_t xeXMsgStartIORequestEx(uint32_t app, uint32_t message, uint32_t overlapped_ptr,
                                uint32_t buffer_ptr, uint32_t buffer_length,
                                XMSGSTARTIOREQUEST_UNKNOWNARG* unknown);
}  // namespace rex::kernel::xam

REX_HOOK_RAW(__imp__XMsgStartIORequest) {
  constexpr uint32_t kXamAppId = 0xFE;
  constexpr uint32_t kMsgQueryVolumeDeviceType = 0x00020021;
  constexpr uint32_t kInvalidArg = 0x80070057;  // X_E_INVALIDARG
  const uint32_t app = ctx.r3.u32;
  const uint32_t message = ctx.r4.u32;
  if (app == kXamAppId && message == kMsgQueryVolumeDeviceType) {
    ctx.r3.u64 = kInvalidArg;
    return;
  }
  ctx.r3.u64 = rex::kernel::xam::xeXMsgStartIORequestEx(
      app, message, ctx.r5.u32, ctx.r6.u32, ctx.r7.u32, nullptr);
}

// ============================================================================
// 2. Hook XeKeysConsolePrivateKeySign (Certificado Retail para firmar cache0XX.map)
// ============================================================================
REX_HOOK_RAW(__imp__XeKeysConsolePrivateKeySign) {
  const uint32_t hash = ctx.r3.u32;
  const uint32_t out = ctx.r4.u32;
  if (!hash || !out) {
    ctx.r3.u64 = 0;
    return;
  }
  uint8_t* cert = base + out;
  std::memset(cert, 0, 0x1A8);  // sizeof(XE_CONSOLE_CERTIFICATE)
  const uint8_t console_id[5] = {0x93, 0x01, 0x64, 0xE6, 0x07};
  std::memcpy(cert + 0x2, console_id, sizeof(console_id));
  cert[0x18] = 0;
  cert[0x19] = 0;
  cert[0x1A] = 0;
  cert[0x1B] = 2;  // Retail
  const uint8_t date[8] = {2, 0, 0, 5, 1, 1, 2, 2};
  std::memcpy(cert + 0x1C, date, sizeof(date));
  ctx.r3.u64 = 1;
}

// ============================================================================
// 3. Hook XeCryptBnQwNeRsaPubCrypt (Validación RSA Big-Endian de mapas .map)
// ============================================================================
namespace {
using Limbs = std::vector<uint32_t>;

uint64_t LoadBE64(const uint8_t* p) {
  uint64_t v = 0;
  for (int i = 0; i < 8; i++) v = (v << 8) | p[i];
  return v;
}

void StoreBE64(uint8_t* p, uint64_t v) {
  for (int i = 7; i >= 0; i--, v >>= 8) p[i] = static_cast<uint8_t>(v);
}

Limbs LoadBn(const uint8_t* p, uint32_t qwords) {
  Limbs out(qwords * 2);
  for (uint32_t i = 0; i < qwords; i++) {
    uint64_t q = LoadBE64(p + i * 8);
    out[i * 2] = static_cast<uint32_t>(q);
    out[i * 2 + 1] = static_cast<uint32_t>(q >> 32);
  }
  return out;
}

void StoreBn(uint8_t* p, const Limbs& v, uint32_t qwords) {
  for (uint32_t i = 0; i < qwords; i++) {
    StoreBE64(p + i * 8, (uint64_t(v[i * 2 + 1]) << 32) | v[i * 2]);
  }
}

int Compare(const Limbs& a, const Limbs& b) {
  for (size_t i = a.size(); i-- > 0;) {
    if (a[i] != b[i]) return a[i] < b[i] ? -1 : 1;
  }
  return 0;
}

void SubInPlace(Limbs& a, const Limbs& b) {
  int64_t borrow = 0;
  for (size_t i = 0; i < a.size(); i++) {
    int64_t d = int64_t(a[i]) - b[i] - borrow;
    borrow = d < 0;
    a[i] = static_cast<uint32_t>(d);
  }
}

Limbs MulMod(const Limbs& a, const Limbs& b, const Limbs& n) {
  const size_t k = n.size();
  std::vector<uint32_t> prod(2 * k, 0);
  for (size_t i = 0; i < k; i++) {
    uint64_t carry = 0;
    for (size_t j = 0; j < k; j++) {
      uint64_t t = uint64_t(a[i]) * b[j] + prod[i + j] + carry;
      prod[i + j] = static_cast<uint32_t>(t);
      carry = t >> 32;
    }
    prod[i + k] = static_cast<uint32_t>(carry);
  }
  Limbs r(k + 1, 0);
  Limbs nn(n);
  nn.push_back(0);
  for (size_t bit = 2 * k * 32; bit-- > 0;) {
    uint32_t carry = (prod[bit / 32] >> (bit % 32)) & 1;
    for (size_t i = 0; i < r.size(); i++) {
      uint32_t next = r[i] >> 31;
      r[i] = (r[i] << 1) | carry;
      carry = next;
    }
    if (Compare(r, nn) >= 0) SubInPlace(r, nn);
  }
  r.pop_back();
  return r;
}
}  // namespace

REX_HOOK_RAW(__imp__XeCryptBnQwNeRsaPubCrypt) {
  const uint8_t* rsa = base + ctx.r5.u32;
  const uint32_t size =
      (uint32_t(rsa[0]) << 24) | (rsa[1] << 16) | (rsa[2] << 8) | rsa[3];
  const uint32_t exponent =
      (uint32_t(rsa[4]) << 24) | (rsa[5] << 16) | (rsa[6] << 8) | rsa[7];
  if (size == 0 || size > 64) {
    ctx.r3.u64 = 0;
    return;
  }
  const Limbs n = LoadBn(rsa + 16, size);
  const Limbs a = LoadBn(base + ctx.r3.u32, size);
  if (Compare(a, n) >= 0) {
    ctx.r3.u64 = 0;
    return;
  }
  Limbs result(n.size(), 0);
  result[0] = 1;
  for (int bit = 31; bit >= 0; bit--) {
    result = MulMod(result, result, n);
    if ((exponent >> bit) & 1) result = MulMod(result, a, n);
  }
  StoreBn(base + ctx.r4.u32, result, size);
  ctx.r3.u64 = 1;
}

// ============================================================================
// 4. Optimización de Spin-Wait de Ultra-Rendimiento para ARM64 Cortex-A57 (Switch)
// ============================================================================
extern "C" void autoport_spin_hint() {
#if defined(__aarch64__)
  __asm__ __volatile__("yield");
#endif
  thread_local uint32_t hints = 0;
  if (++hints >= 2048) {
    hints = 0;
    std::this_thread::yield();
  }
}

// ============================================================================
// 5. Direct3D Command Ring Wait (sub_826C5990)
//    Cuando el buffer de comandos de la GPU está lleno (r3 == 1), cede tiempo
//    para que el CommandProcessor de Vulkan vacíe los paquetes PM4 sin trabar la CPU.
// ============================================================================
REX_EXTERN(__imp__sub_826C5990);
extern "C" REX_FUNC(sub_826C5990) {
  __imp__sub_826C5990(ctx, base);
  if (ctx.r3.u32 == 1) {
    thread_local uint32_t wait_steps = 0;
    if (++wait_steps < 8) {
#if defined(__aarch64__)
      __asm__ volatile("yield" ::: "memory");
#endif
    } else {
      wait_steps = 0;
      std::this_thread::yield();
    }
  }
}

// ============================================================================
// 6. XMA Audio Hardware Context Polling (sub_8292DA80)
//    Cuando el hardware XMA no está listo (r3 == 0), cede el turno para que el
//    hilo host XMA Decoder decodifique los paquetes de audio inmediatamente.
// ============================================================================
REX_EXTERN(__imp__sub_8292DA80);
extern "C" REX_FUNC(sub_8292DA80) {
  __imp__sub_8292DA80(ctx, base);
  if (ctx.r3.u32 == 0) {
    thread_local uint32_t wait_steps = 0;
    if (++wait_steps < 8) {
#if defined(__aarch64__)
      __asm__ volatile("yield" ::: "memory");
#endif
    } else {
      wait_steps = 0;
      std::this_thread::yield();
    }
  }
}

// ============================================================================
// 7. Funciones GapFill no registradas (0x82240218 y 0x82241910)
//    Puntos de entrada TLS para llamadas indirectas del motor omaha_release
// ============================================================================
#include <rex/runtime.h>
#include <rex/system/function_dispatcher.h>

extern "C" REX_FUNC(sub_82240218) {
  if (base && ctx.r13.u32) {
    ctx.r10.u64 = __builtin_bswap32(*reinterpret_cast<volatile uint32_t*>(base + ctx.r13.u32));
  } else {
    ctx.r10.u64 = 0;
  }
  ctx.r3.u64 = 0;
}

extern "C" REX_FUNC(sub_82241910) {
  if (base && ctx.r13.u32) {
    ctx.r10.u64 = __builtin_bswap32(*reinterpret_cast<volatile uint32_t*>(base + ctx.r13.u32));
  } else {
    ctx.r10.u64 = 0;
  }
  ctx.r3.u64 = 0;
}

void RegisterMissingFunctions(rex::Runtime* rt) {
  if (rt && rt->function_dispatcher()) {
    rt->function_dispatcher()->SetFunction(0x82240218, sub_82240218);
    rt->function_dispatcher()->SetFunction(0x82241910, sub_82241910);
  }
}
