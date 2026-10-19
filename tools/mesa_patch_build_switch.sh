#!/usr/bin/env bash
# Parchea build-switch.sh de danfromtico/mesa-switch para compilar en modo no interactivo (-Doptimization=2)
# y empaquetar libvulkan.a + libnak_rs.a con aarch64-none-elf-ar -M.
set -euo pipefail

MESA_SRC="${1:-mesa_src}"
if [ ! -f "$MESA_SRC/build-switch.sh" ]; then
    echo "Error: No se encontró $MESA_SRC/build-switch.sh" >&2
    exit 1
fi

sed -i 's/docker run -it/docker run --rm/g' "$MESA_SRC/build-switch.sh"
sed -i -E 's/-Doptimization=[0-9sg]+/-Doptimization=2/g' "$MESA_SRC/build-switch.sh"
echo "[mesa_patch_build_switch] build-switch.sh actualizado (-Doptimization=2, modo CI sin TTY)."
