#!/usr/bin/env bash
# Fase 3: Ejecuta el bucle convergente de autoport + rexglue codegen sobre project/haloreach_manifest.toml
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REXGLUE_BIN="${REXGLUE_BIN:-$ROOT/build_host_sdk/bin/rexglue}"
AP="$ROOT/tools/autoport"
MANIFEST="$ROOT/project/haloreach_manifest.toml"

if [ ! -x "$REXGLUE_BIN" ]; then
    echo "Error: No se encontró el binario host $REXGLUE_BIN. Ejecuta primero tools/setup_deps.sh" >&2
    exit 1
fi

mkdir -p "$ROOT/project/config"

echo "== [1/7] Resolviendo saltos tail-merged e iterando rexglue codegen..."
python3 "$AP/fix_unresolved.py" "$MANIFEST" --rexglue "$REXGLUE_BIN"

echo "== [2/7] Escaneando funciones huérfanas (vtables / callbacks sin .pdata)..."
python3 "$AP/scan_orphans.py" "$MANIFEST"

echo "== [3/7] Detectando fibras XAPI (CreateFiber / SwitchToFiber / ConvertThreadToFiber)..."
python3 "$AP/detect_xapi.py" "$MANIFEST"

echo "== [4/7] Re-convergiendo codegen con huérfanos y fibras XAPI..."
python3 "$AP/fix_unresolved.py" "$MANIFEST" --rexglue "$REXGLUE_BIN"

echo "== [5/7] Verificando y corrigiendo jump tables truncadas (fix_switch_tables.py)..."
if python3 "$AP/fix_switch_tables.py" "$MANIFEST" | grep -q " -> "; then
    python3 "$AP/fix_unresolved.py" "$MANIFEST" --rexglue "$REXGLUE_BIN"
fi

echo "== [6/7] Generando thunks cross-DLL para Waves Audio DSP y parches de spinloop..."
python3 "$AP/gen_xdll_imports.py" "$MANIFEST" --log "$ROOT/project/codegen_auto.log"
python3 "$AP/patch_spin_hints.py" "$MANIFEST"

echo "== [7/7] Aplicando parches de código generado para devkitA64 GCC (prepare_switch_codegen.py)..."
python3 "$ROOT/tools/prepare_switch_codegen.py"

echo "== Codegen completo y verificado en project/generated/"
