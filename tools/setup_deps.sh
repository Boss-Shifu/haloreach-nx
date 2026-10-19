#!/usr/bin/env bash
# Fase 2: Clona ReXGlue SDK (con soporte Switch), descarga thirdparty y aplica los 3 parches obligatorios para Horizon OS
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPS_DIR="${DEPS_DIR:-$ROOT/deps}"
SDK_DIR="$DEPS_DIR/rexglue-sdk"

mkdir -p "$DEPS_DIR"

if [ ! -d "$SDK_DIR/include" ]; then
    echo "== Clonando ReXGlue SDK con soporte Nintendo Switch..."
    git clone --depth 1 https://github.com/Gabrick75/fh2-recompiled.git "$DEPS_DIR/fh2-recompiled-tmp"
    rm -rf "$SDK_DIR"
    mv "$DEPS_DIR/fh2-recompiled-tmp/sdk" "$SDK_DIR"
    rm -rf "$DEPS_DIR/fh2-recompiled-tmp"
fi

if [ ! -f "$SDK_DIR/thirdparty/fmt/include/fmt/format.h" ]; then
    echo "== Descargando thirdparty de ReXGlue SDK v0.10.0..."
    python3 "$ROOT/tools/fetch_thirdparty.py" --target "$SDK_DIR/thirdparty"
fi

echo "== Aplicando parches de SDK para Nintendo Switch (Halo: Reach)..."
python3 "$ROOT/tools/patch_sdk_commit_granularity.py" "$SDK_DIR"
python3 "$ROOT/tools/patch_sdk_nullpage.py" "$SDK_DIR"
python3 "$ROOT/tools/patch_sdk_static_modules.py" "$SDK_DIR"

echo "== Compilando herramienta host rexglue (codegen)..."
cmake -S "$SDK_DIR" -B "$ROOT/build_host_sdk" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=clang \
    -DCMAKE_CXX_COMPILER=clang++
cmake --build "$ROOT/build_host_sdk" --target rexglue -j "$(nproc 2>/dev/null || echo 4)"

mkdir -p "$ROOT/build_host_sdk/bin"
BUILT_REXGLUE=""
for cand in "$ROOT/build_host_sdk/bin/rexglue" "$ROOT/build_host_sdk/rexglue" "$SDK_DIR"/out/*/rexglue "$SDK_DIR"/out/*/Release/rexglue; do
    if [ -x "$cand" ]; then
        BUILT_REXGLUE="$cand"
        break
    fi
done

if [ -z "$BUILT_REXGLUE" ]; then
    BUILT_REXGLUE="$(find "$ROOT/build_host_sdk" "$SDK_DIR/out" -type f -name rexglue -executable 2>/dev/null | head -n 1 || true)"
fi

if [ -z "$BUILT_REXGLUE" ]; then
    echo "Error: No se encontró el ejecutable rexglue tras compilar el SDK." >&2
    exit 1
fi

if [ "$BUILT_REXGLUE" != "$ROOT/build_host_sdk/bin/rexglue" ]; then
    cp -f "$BUILT_REXGLUE" "$ROOT/build_host_sdk/bin/rexglue"
    chmod +x "$ROOT/build_host_sdk/bin/rexglue"
fi

echo "== SDK listo y herramienta rexglue en: $ROOT/build_host_sdk/bin/rexglue"
