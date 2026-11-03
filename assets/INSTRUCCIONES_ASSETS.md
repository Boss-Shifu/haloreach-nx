# Instrucciones de Extracción de Assets (BYOG - Bring Your Own Game)

Este repositorio **NO CONTIENE NINGÚN ARCHIVO CON DERECHOS DE AUTOR** ni binarios propietarios de Microsoft o Bungie.
Para poder compilar y ejecutar este port en tu Nintendo Switch, debes suministrar los archivos de tu propia copia legal de **Halo: Reach** para Xbox 360.

## ¿Qué archivos necesitas colocar en `assets/game_root/`?

1. Extrae tu copia legal de *Halo: Reach* de Xbox 360 (disco original o volcado digital).
2. Coloca los siguientes archivos binarios en `assets/game_root/`:
   * `default.xex` (Ejecutable principal del juego).
   * `WaveShell-Xbox.dll`
   * `WavesLibDLL.dll`
   * `waves/L360.dll`
   * `waves/Q10.dll`

## Proceso de Generación de Código (ReXGlue SDK)

Una vez colocados los binarios anteriores en `assets/game_root/`, utiliza la herramienta de recompilación estática ReXGlue para generar el código C++ en `project/generated/`:

```bash
# Ejemplo de ejecución del generador de código AOT con ReXGlue:
bash tools/codegen.sh
```

El script tomará el binario `default.xex` y los módulos auxiliares de audio y generará los archivos `.cpp` correspondientes dentro de `project/generated/default/`.

Posteriormente podrás compilar el ejecutable de Nintendo Switch (`haloreach.nro`) siguiendo las instrucciones del `README.md`.
