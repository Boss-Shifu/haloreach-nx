# Halo: Reach NX — Nintendo Switch Port (Recompilación Estática AOT)

Port nativo para **Nintendo Switch** de **Halo: Reach** (Xbox 360, Title ID `4D53085B`, versión *omaha_release 11860* en Español), ejecutado mediante **recompilación estática nativa (Ahead-of-Time - AOT)** con el runtime **ReXGlue SDK** y renderizado nativo sobre **Vulkan 1.3 + Mesa NVK**.

---

## 🎮 Visión General

A diferencia de la emulación tradicional que interpreta o recompila código en tiempo de ejecución (JIT) consumiendo enormes recursos de CPU, este proyecto traduce estáticamente el código máquina PowerPC Xenon (3 núcleos / 6 hilos) de Xbox 360 a código nativo **C++ / ARM64 (AArch64)**.

El subsistema gráfico se apoya en un renderizador nativo Xenos a Vulkan (arquitectura probada en *F.E.A.R. NX* y *Need for Speed: Most Wanted NX*), eliminando por completo la simulación pesada de memoria EDRAM en CPU y permitiendo que la GPU Nvidia Tegra X1 dibuje directamente mediante llamadas Vulkan sobre el driver libre **Mesa NVK**.

---

## 🚀 Estado Actual del Port

* **Menús y Navegación:** Funcionando de forma fluida a **40 – 60 FPS**.
* **Audio:** Decodificación nativa de streams multicanal **XMA** mediante hilos de trabajo asíncronos en tiempo real, sin entrecortes.
* **Cinemáticas y 3D:** Carga cinemáticas en tiempo real (misión `m05`) y escenas 3D (el casco de Noble Six en el terreno, el planeta Reach orbitando en 3D) entre **20 y 30 FPS**.
* **Idioma:** Configurado y optimizado para la versión en **Español** (voces de doblaje latino/castellano y textos de interfaz).

---

## 🛠️ Modificaciones e Ingenierías Implementadas

A lo largo del desarrollo de este port se implementaron soluciones críticas para adaptar el motor *Blam!* de Bungie a la arquitectura de Nintendo Switch:

### 1. Renderizador Nativo Vulkan (`project/src/native/`)
* **Migración de backend gráfico:** Se desacopló el renderizador emulado tradicional para integrar la infraestructura de renderizado nativo de Xenos en C++ (`native_renderer.cpp`, `native_system.cpp`, `native_textures.cpp`, `native_geometry_shaders.cpp`).
* **Traducción AOT de Shaders:** Empleo del traductor de microcódigo Xenos a SPIR-V compatible con Vulkan 1.3 sin necesidad de pre-compilar bibliotecas manuales masivas.
* **Shaders de Cómputo Auxiliares:**
  * `copy_color.cs.glsl`: Copias rápidas de búferes de color entre áreas de resolución.
  * `depth_resolve.cs.glsl`, `depth_msaa_to_float.cs.glsl`, `depth_to_float.cs.glsl`: Conversión de formatos de profundidad `kD24S8` y `kD24FS8` hacia texturas muestreables por la GPU.
* **Caché persistente en microSD:** Habilitación de la caché binaria de shaders de Mesa (`sdmc:/switch/HaloReach/userdata/cache/mesa`) para eliminar tirones (*stutter*) y tiempos de espera de compilación.

### 2. Gestión de Memoria y Presupuesto de Heap en Horizon OS (`switch/CMakeLists.txt`)
* **Ajuste de Heap a 1024 MB:** Se fijó el heap del binario en `HR_SWITCH_HEAP_MB = 1024`. En modo *Title Takeover* (~3.2 GB utilizables), esto deja más de 2 GB de espacio de direccionamiento libre para que el driver **Mesa NVK** gestione el espacio de memoria unificado GPU/CPU sin agotar la memoria virtual de Horizon OS.
* **Boost de Límite de Hilos:** Llamada explícita a `pmshellBoostApplicationThreadResourceLimit()` en el arranque para permitir hasta 256 hilos nativos sin bloqueos en el kernel de la consola.

### 3. Resolución Interna y Escalado a 540p (`haloreach_app.h` y `config/haloreach.toml`)
* Para maximizar la tasa de cuadros por segundo en la GPU Tegra X1, se desacopló la resolución interna de renderizado:
  * `video_mode_width = 1280` / `video_mode_height = 720` (Modo de vídeo del juego huésped).
  * `window_width = 960` / `window_height = 540` (Resolución de salida interna en 540p).
  * Presentador con escalado bilinear a pantalla completa (*widescreen 16:9*).

### 4. Optimizaciones de CPU y Sincronización ARM64 (`haloreach_hooks.cpp`)
* **Yield en Spin-Wait:** `autoport_spin_hint()` ejecuta instrucciones ensamblador `yield` y cede cooperativamente el hilo con `std::this_thread::yield()` cada 2048 iteraciones, evitando que los 3 núcleos Cortex-A57 se saturen al 100% en bucles vacíos de espera.
* **D3D Command Ring Wait (`sub_826C5990`):** Cuando el anillo de paquetes PM4 de la GPU se llena, cede el turno en CPU para permitir que el despachador de Vulkan drene los comandos pendientes.
* **XMA Hardware Polling (`sub_8292DA80`):** Cede tiempo al hilo de decodificación de audio cuando los contextos XMA están en espera.
* **GapFill de llamadas indirectas:** Reimplementación de `sub_82240218` y `sub_82241910` para lecturas de almacenamiento local de hilo (TLS en `r13`).

### 5. Sistema de Archivos VFS y Streaming de Mapas (`haloreach_app.h`)
* Montaje dinámico de los enlaces simbólicos del sistema de archivos de Xbox 360:
  * `\CACHE0`, `\CACHE1`, `\CACHE` $\rightarrow$ `userdata/cache_partitions/`
  * `\XSTORAGE`, `\MU` $\rightarrow$ almacenamiento de preferencias y datos del usuario.

---

## 🔍 Problemas Conocidos y Tareas para la Comunidad (To-Do List)

Invitamos a programadores de la comunidad, especialistas en ingeniería inversa, Vulkan y Horizon OS a colaborar en los siguientes puntos clave:

### 1. Corrección del Color/Fondo en Renderizado HDR (Cielo/Espacio Blanco y Destellos)
* **Síntoma:** El espacio exterior en la órbita de Reach y el cielo detrás de la escena inicial se muestran de color blanco brillante con aberraciones amarillas/rojas en los bordes de los modelos 3D, y dentro de la nave Pelican aparece un destello horizontal blanquecino/rojizo.
* **Causa Identificada:** Halo: Reach utiliza un búfer de color HDR de alta precisión (`k_2_10_10_10_FLOAT_AS_16_16_16_16`, formato 2 en Xenos). Los pases de cálculo de luminancia y adaptación de exposición utilizan texturas 1x1 y operaciones de borrado que interactúan con el búfer de profundidad. Al intentar desacoplar o espejar borrados en `native_renderer.cpp`, se pierde el fondo o se desalinea el refresco de los menús.
* **Objetivo:** Implementar la decodificación correcta de borrado y el pipeline de exposición/mapeo tonal HDR en `native_renderer.cpp` sin interferir con el borrado de pantalla de la interfaz.

### 2. Bypass de Verificación de Estado de Campaña (Bucle de cinemática `m05`)
* **Síntoma:** Al terminar la cinemática de apertura `m05`, el juego vuelve al fondo del planeta Reach e inicia la cinemática en bucle sin entrar a la misión `m10` (*Winter Contingency*).
* **Causa Identificada:** La función `sub_82429300` realiza una comprobación de integridad criptográfica (SHA-1) sobre el estado de la campaña y consulta secciones del módulo firmado (`sub_82206240`). Al no encontrar un binario XEX con firma RSA válida, aborta la transición de mapa.
* **Objetivo:** Enganchar (*hook*) o parchear limpiamente `sub_82429300` y `sub_82206240` para que certifiquen el inicio de la campaña como válido sin corromper el stack ni las estructuras de guardado.

### 3. Implementación de Memexport en Vertex Shaders
* **Síntoma:** En ciertos modelos y armaduras de Spartans (o efectos de partículas), la geometría no se renderiza completa (por ejemplo, piezas del casco o blindaje faltante).
* **Causa Identificada:** En `native_renderer.cpp`, las llamadas de dibujo cuyos shaders escriben en memoria de exportación (`vs->memexport_eM_written()`) se descartan con `fail(2)`.
* **Objetivo:** Mapear los flujos de *memexport* a Storage Buffers (SSBO) de Vulkan o canalizar los cálculos de transformación de vértices a un paso de cómputo previo.

### 4. Estabilización de Framerate a 30 / 60 FPS
* **Objetivo:** Optimizar las barreras de sincronización (`VkPipelineBarrier`) en la presentación de fotogramas, reduciendo la sobrecarga de CPU en el Command Processor para alcanzar 30 FPS sólidos en gameplay y 60 FPS en escenarios lineales.

---

## 📦 Estructura del Proyecto

```
haloreach-nx/
├── config/
│   └── haloreach.toml           # Configuración de runtime (resolución, CVARs, audio, Vulkan)
├── deps/
│   └── rexglue-sdk/             # SDK de ReXGlue con subsistemas de kernel, XAM y threading
├── project/
│   ├── generated/               # Código C++ generado por el recompilador estático
│   └── src/
│       ├── haloreach_app.h      # Ciclo de vida de la aplicación, configuración VFS y arranque
│       ├── haloreach_hooks.cpp  # Hooks específicos de Halo Reach (D3D, audio, spin-wait)
│       └── native/              # Renderizador nativo Xenos a Vulkan (Mesa NVK)
│           ├── native_renderer.cpp
│           ├── native_textures.cpp
│           ├── native_system.cpp
│           └── shaders/         # Shaders de cómputo en GLSL y cabeceras SPIR-V
└── switch/
    └── CMakeLists.txt           # Configuración de compilación para devkitA64 / Nintendo Switch
```

---

## 🔧 Requisitos y Compilación

### Requisitos previos
* **devkitPro** con toolchain `devkitA64` y bibliotecas `libnx`.
* **CMake 3.24+** y **Ninja**.
* Entorno de compilación cruzada para `aarch64-none-elf`.

### Instrucciones de compilación
1. Clonar el repositorio:
   ```bash
   git clone https://github.com/Boss-Shifu/haloreach-nx.git
   cd haloreach-nx
   ```
2. Generar el entorno de compilación:
   ```bash
   cmake -B build_switch -S switch -G Ninja -DCMAKE_TOOLCHAIN_FILE=C:/devkitPro/cmake/Switch.cmake -DCMAKE_BUILD_TYPE=Release
   ```
3. Compilar el ejecutable para Switch (`.nro`):
   ```bash
   cmake --build build_switch -j 8
   ```
   El binario resultante se encontrará en `build_switch/haloreach.nro`.

---

## 📲 Instalación en Nintendo Switch

1. Copia la carpeta del juego a la tarjeta microSD de tu consola:
   ```
   sdmc:/switch/HaloReach/
   ├── haloreach.nro
   ├── haloreach.toml
   ├── default.xex (o assets del juego original extraídos)
   └── userdata/
   ```
2. **IMPORTANTE (Title Takeover Obligatorio):**
   * **NUNCA** ejecutes el juego desde el Modo Álbum (*Applet Mode*, límite de 400 MB).
   * Mantén presionado el botón **R** al iniciar cualquier juego instalado en el menú principal de tu consola para acceder al Homebrew Menu con acceso a los **3.2 GB de memoria RAM**.

---

## 📄 Créditos y Licencias

* **Bungie & Microsoft Game Studios:** Creadores del juego original *Halo: Reach*.
* **ReXGlue Project:** Runtime y SDK de recompilación estática para Xbox 360.
* **Comunidad de Porting de Nintendo Switch:** Proyectos base de renderizado nativo derivados de *F.E.A.R. NX* y *Need for Speed: Most Wanted NX*.
* **Mesa / NVK:** Driver Vulkan de código abierto para GPU Nvidia Tegra X1.
