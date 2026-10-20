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
    rex::cvar::SetFlagByName("gpu_plugin", "xenos");
    rex::cvar::SetFlagByName("mount_cache", "true");
    rex::cvar::SetFlagByName("allow_game_relative_writes", "true");
    rex::cvar::SetFlagByName("gpu_allow_invalid_fetch_constants", "true");
    rex::cvar::SetFlagByName("execute_unclipped_draw_vs_on_cpu", "true");
    rex::cvar::SetFlagByName("vsync", "false");
    rex::cvar::SetFlagByName("vulkan_allow_present_mode_immediate", "true");
    rex::cvar::SetFlagByName("present_esperar_adquisicion_en_cpu", "false");
    rex::cvar::SetFlagByName("render_target_path_vulkan", "fsi");
    rex::cvar::SetFlagByName("present_effect", "fsr");
    rex::cvar::SetFlagByName("fsr_sharpness", "0.25");
    rex::cvar::SetFlagByName("protect_zero", "false");
    if (!rex::cvar::HasNonDefaultValue("window_width")) {
      rex::cvar::SetFlagByName("window_width", "1280");
    }
    if (!rex::cvar::HasNonDefaultValue("window_height")) {
      rex::cvar::SetFlagByName("window_height", "720");
    }
    if (!rex::cvar::HasNonDefaultValue("video_mode_width")) {
      rex::cvar::SetFlagByName("video_mode_width", "960");
    }
    if (!rex::cvar::HasNonDefaultValue("video_mode_height")) {
      rex::cvar::SetFlagByName("video_mode_height", "540");
    }
    if (!rex::cvar::HasNonDefaultValue("video_mode_width")) {
      rex::cvar::SetFlagByName("video_mode_width", "960");
    }
    if (!rex::cvar::HasNonDefaultValue("video_mode_height")) {
      rex::cvar::SetFlagByName("video_mode_height", "540");
    }
    // Evitar doble caché de shaders en la microSD con Mesa NVK
    setenv("MESA_SHADER_CACHE_DISABLE", "1", 0);
    setenv("NOUVEAU_HORIZON_BO_CACHE_MB", "192", 0);
    HaloReachInitHooks();
  }

  void OnPostSetup() override {
    MountHaloReachCachePartitions(runtime());
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
      auto device = std::make_unique<rex::filesystem::HostPathDevice>(
          m.device, host, false, true);
      if (!device->Initialize()) continue;
      rt->file_system()->RegisterDevice(std::move(device));
      rt->file_system()->RegisterSymbolicLink(m.link, m.device);
    }
  }
};
