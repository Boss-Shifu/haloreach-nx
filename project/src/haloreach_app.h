#include "native/native_system.h"
// haloreach - ReXGlue Statically Recompiled Project for Nintendo Switch (Title ID 4D53085B)
// Combines Gabrick75 ReXGlue 0.10.0 Switch SDK + xenon-pc-comp Halo: Reach runtime fixes.

#pragma once

#include <rex/cvar.h>
#include <rex/filesystem/devices/host_path_device.h>
#include <rex/filesystem/vfs.h>
#include <rex/rex_app.h>
#include <rex/runtime.h>
#include <rex/ui/presenter.h>

#include <cstdlib>
#include <filesystem>
#include <memory>

void HaloReachInitHooks();
void RegisterMissingFunctions(rex::Runtime* rt);

class HaloReachApp : public rex::ReXApp {
 public:
  using rex::ReXApp::ReXApp;

  static std::unique_ptr<rex::ui::WindowedApp> Create(
      rex::ui::WindowedAppContext& ctx) {
    return std::unique_ptr<HaloReachApp>(new HaloReachApp(
        ctx, "haloreach", PPCImageConfig));
  }

  void OnConfigurePaths(rex::PathConfig& paths) override {
#if defined(REX_PLATFORM_SWITCH) || defined(__SWITCH__)
    const auto folder = rex::filesystem::GetExecutableFolder();
    if (!folder.empty()) {
      if (paths.game_data_root.empty()) {
        paths.game_data_root = folder / "game_root";
      }
      paths.user_data_root = folder / "userdata";
      paths.cache_root = folder / "userdata/cache";
      paths.config_path = folder / "haloreach.toml";
    }
#endif
  }

  void OnPostInitLogging() override {
    // Forzar plugin GPU xenos para asegurar que la emulación gráfica no inicie vacía
    if (!rex::cvar::HasNonDefaultValue("gpu_plugin") || rex::cvar::GetFlagByName("gpu_plugin").empty()) {
      rex::cvar::SetFlagByName("gpu_plugin", "xenos");
    }
  }

  void OnPreSetup(rex::RuntimeConfig& config) override {
 if (reach_nx::native::Enabled()) {
 config.graphics = reach_nx::native::CreateGraphicsSystem();
 }
    rex::cvar::SetFlagByName("gpu_plugin", "xenos");
    rex::cvar::SetFlagByName("mount_cache", "true");
    rex::cvar::SetFlagByName("allow_game_relative_writes", "true");
    rex::cvar::SetFlagByName("gpu_allow_invalid_fetch_constants", "true");
    rex::cvar::SetFlagByName("execute_unclipped_draw_vs_on_cpu", "false");
    rex::cvar::SetFlagByName("gpu_sin_msaa", "true");
    rex::cvar::SetFlagByName("native_2x_msaa", "false");
    rex::cvar::SetFlagByName("gpu_atalho_resolve", "true");
    // Compilar pipelines en hilos trabajadores: con "false" cada permutacion VS/PS
    // bloquea el hilo del procesador de comandos (NAK -> SASS en Tegra X1).
    rex::cvar::SetFlagByName("async_shader_compilation", "true");
    rex::cvar::SetFlagByName("readback_memexport", "false");
    rex::cvar::SetFlagByName("readback_memexport_fast", "false");
    rex::cvar::SetFlagByName("readback_resolve", "none");
    rex::cvar::SetFlagByName("occlusion_query_enable", "false");
    rex::cvar::SetFlagByName("clear_memory_page_state", "false");
    rex::cvar::SetFlagByName("gpu_escala_render", "75");
    rex::cvar::SetFlagByName("vblank_adaptativo", "true");
    rex::cvar::SetFlagByName("audio_switch_tramas_en_cola", "8");
    rex::cvar::SetFlagByName("audio_xma_en_trabajador", "1");
    rex::cvar::SetFlagByName("audio_switch_bomba", "true");
    // vsync=true es OBLIGATORIO para el rendimiento en Switch: con vsync=false el
    // hilo "GPU VSync" sintetiza un vblank cada 1 ms (1000 Hz) en lugar de 60 Hz,
    // despertando 16x mas veces al invitado y al procesador de comandos.
    rex::cvar::SetFlagByName("vsync", "true");
    rex::cvar::SetFlagByName("vulkan_allow_present_mode_immediate", "true");
    rex::cvar::SetFlagByName("present_esperar_adquisicion_en_cpu", "false");
    rex::cvar::SetFlagByName("render_target_path_vulkan", "fbo");
    rex::cvar::SetFlagByName("present_effect", "bilinear");
    rex::cvar::SetFlagByName("present_letterbox", "true");
    rex::cvar::SetFlagByName("protect_zero", "false");
    rex::cvar::SetFlagByName("window_width", "960");
    rex::cvar::SetFlagByName("window_height", "540");
    rex::cvar::SetFlagByName("video_mode_width", "1280");
    rex::cvar::SetFlagByName("video_mode_height", "720");
    rex::cvar::SetFlagByName("nx_native_msaa", "false");
    rex::cvar::SetFlagByName("nx_native_max_anisotropy", "2");
    rex::cvar::SetFlagByName("nx_native_texture_min_mip", "1");
    rex::cvar::SetFlagByName("log_async", "true");
    rex::cvar::SetFlagByName("log_level", "info");
    rex::cvar::SetFlagByName("user_language", "5");
    rex::cvar::SetFlagByName("user_country", "154");
    // Habilitar caché persistente de shaders Mesa NVK en la microSD para eliminar 5 minutos de espera
    setenv("MESA_SHADER_CACHE_DISABLE", "0", 1);
    // La ruta necesita el prefijo de dispositivo sdmc:; newlib no resuelve "/switch/...".
    setenv("MESA_SHADER_CACHE_DIR", "sdmc:/switch/HaloReach/userdata/cache/mesa", 1);
    setenv("MESA_SHADER_CACHE_MAX_SIZE", "512M", 1);
    setenv("NOUVEAU_HORIZON_BO_CACHE_MB", "192", 1);
    HaloReachInitHooks();
  }

  void OnPostSetup() override {
    MountHaloReachCachePartitions(runtime());
    RegisterMissingFunctions(runtime());
  }

 private:
  // Halo: Reach copia mapas a cache0:\cache0XX.map y hace streaming de texturas desde ahí.
  // Si cache0:/cache1:/cache: no están montados en el VFS, las texturas 3D no cargan.
  static void MountHaloReachCachePartitions(rex::Runtime* rt) {
    if (!rt || !rt->file_system()) return;
    const std::filesystem::path root = rt->user_data_root() / "cache_partitions";
    struct Mount {
      const char* device;
      const char* link;
      const char* dir;
    };
    for (const Mount& m : {
             Mount{"\\CACHE0", "cache0:", "cache0"},
             Mount{"\\CACHE1", "cache1:", "cache1"},
             Mount{"\\CACHE", "cache:", "cache"},
             Mount{"\\XSTORAGE", "xstorage:", "xstorage"},
             Mount{"\\MU", "mu:", "mu"},
         }) {
      const auto host = root / m.dir;
      std::error_code ec;
      std::filesystem::create_directories(host, ec);
      if (std::string(m.dir) == "cache0") {
        const auto pref = host / "preferences.dat";
        if (!std::filesystem::exists(pref)) {
          FILE* fp = fopen(pref.string().c_str(), "wb");
          if (fp) fclose(fp);
        }
      }
      auto device = std::make_unique<rex::filesystem::HostPathDevice>(
          m.device, host, false, true);
      if (!device->Initialize()) continue;
      rt->file_system()->RegisterDevice(std::move(device));
      rt->file_system()->RegisterSymbolicLink(m.link, m.device);
      rt->file_system()->RegisterSymbolicLink(std::string(m.link) + "\\", m.device);
      rt->file_system()->RegisterSymbolicLink(std::string("\\??\\") + m.link, m.device);
      rt->file_system()->RegisterSymbolicLink(std::string("\\??\\") + m.link + "\\", m.device);
    }
  }
};
