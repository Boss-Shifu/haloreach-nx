// static_modules.cpp — Registro estático de los 4 módulos DLL XEX2 de Halo: Reach en Nintendo Switch
// En Horizon OS (Switch) dlopen() no existe; los 4 módulos DSP de audio (WaveShell, WavesLib, L360, Q10)
// se compilan estáticamente con símbolos prefijados y se registran aquí para LoadUserModule().

#include <cstdint>
#include <cstring>
#include <string_view>

struct StaticRexModuleEntry {
  const char* guest_name;
  const void* image_info;
  void (*register_fn)();
};

#if defined(HALOREACH_LINK_STATIC_MODULES)
extern "C" {
const void* waveshell_xbox_ReXModule_GetImageInfo();
void waveshell_xbox_ReXModule_Register();

const void* waveslibdll_ReXModule_GetImageInfo();
void waveslibdll_ReXModule_Register();

const void* l360_ReXModule_GetImageInfo();
void l360_ReXModule_Register();

const void* q10_ReXModule_GetImageInfo();
void q10_ReXModule_Register();
}
#endif

extern "C" const StaticRexModuleEntry* rex_find_static_module(const char* name) {
  if (!name) return nullptr;
  // Extraer solo el nombre base en minúsculas (sin ruta d:\ ni waves\)
  const char* base = name;
  for (const char* p = name; *p; ++p) {
    if (*p == '\\' || *p == '/') base = p + 1;
  }
#if defined(HALOREACH_LINK_STATIC_MODULES)
  static const StaticRexModuleEntry kTable[] = {
      {"waveshell-xbox.dll", reinterpret_cast<const void*>(&waveshell_xbox_ReXModule_GetImageInfo), &waveshell_xbox_ReXModule_Register},
      {"waveslibdll.dll", reinterpret_cast<const void*>(&waveslibdll_ReXModule_GetImageInfo), &waveslibdll_ReXModule_Register},
      {"l360.dll", reinterpret_cast<const void*>(&l360_ReXModule_GetImageInfo), &l360_ReXModule_Register},
      {"q10.dll", reinterpret_cast<const void*>(&q10_ReXModule_GetImageInfo), &q10_ReXModule_Register},
  };
  for (const auto& entry : kTable) {
    if (strcasecmp(base, entry.guest_name) == 0) {
      return &entry;
    }
  }
#endif
  return nullptr;
}
