#!/usr/bin/env bash
# Orquestador completo de las Fases 2, 3, 5 y 6 dentro del contenedor devkitpro/devkita64
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "========================================================"
echo "  Halo: Reach NX (4D53085B) — Pipeline de Recompilación "
echo "  Target: 60 FPS @ OC 1750 MHz CPU / 765 MHz GPU / 2600 RAM"
echo "========================================================"

bash "$ROOT/tools/setup_deps.sh"
bash "$ROOT/tools/codegen.sh"
bash "$ROOT/tools/build_nro.sh"
