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
    // newlib no considera "sdmc:/..." como ruta absoluta y el SDK le antepone la
    // carpeta del NRO (sdmc:/switch/HaloReach/sdmc:/...). Usar rutas relativas al NRO.
    if (paths.game_data_root.empty()) {
      paths.game_data_root = "game_root";
    }
    paths.user_data_root = "userdata";
    paths.cache_root = "userdata/cache";
#endif
  }

  void OnPreSetup(rex::RuntimeConfig& config) override {
    rex::cvar::SetFlagByName("mount_cache", "true");
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
