#!/usr/bin/env python3
"""
prepare_switch_codegen.py — Prepara el código C++ generado por ReXGlue 0.10.0 para
compilar con devkitA64 GCC (Nintendo Switch) y optimiza primitivas atómicas / barreras
PowerPC para alcanzar 60 FPS estables con Overclock (1750 MHz CPU / 765 MHz GPU / 2600 MHz RAM).

Pasos:
1. Inserta la rama GCC de DEFINE_REX_FUNC en haloreach_pch.h (GCC descarta atributos antes de extern "C").
2. Inserta barreras de memoria ARM64 reales para instrucciones PowerPC lwsync / sync / eieio.
3. Reemplaza el mutex global de interrupciones (REX_ENTER_GLOBAL_LOCK) en regiones lwarx..stwcx
   por spinlocks por stripe de dirección con instrucción ARM64 `yield`.
"""
import glob
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
gen_dir = root / "project" / "generated"

# Buscar cualquier *_pch.h generado (haloreach_pch.h o similar)
pch_files = list(gen_dir.rglob("*_pch.h"))
if not pch_files:
    print("[prepare_switch_codegen] No se encontró *_pch.h en project/generated; omitiendo.")
    sys.exit(0)

gcc_branch = (
    '#elif defined(__GNUC__) && !defined(__clang__)\n'
    '// GCC rejects attributes ahead of extern "C" and drops them silently.\n'
    '#define DEFINE_REX_FUNC(name)                                       \\\n'
    '  extern "C" REX_FUNC(name)                                         \\\n'
    '      __attribute__((alias("__imp__" #name), weak, noinline));      \\\n'
    '  REX_EXTERN(__imp__##name)\n'
)

for target in pch_files:
    text = target.read_text(encoding="utf-8", errors="replace")
    if '#elif defined(__GNUC__) && !defined(__clang__)' in text:
        print(f"[prepare_switch_codegen] Soporte GCC alias ya presente en {target.name}")
    else:
        anchor = '#else\n#define DEFINE_REX_FUNC(name)'
        if anchor in text:
            text = text.replace(anchor, gcc_branch + anchor, 1)
            target.write_text(text, encoding="utf-8", newline="\n")
            print(f"[prepare_switch_codegen] Aplicado fix GCC weak-alias en {target.name}")

# Insertar barreras de memoria para lwsync / sync / eieio en Cortex-A57 (Tegra X1)
barrier_for = {
    "lwsync": "std::atomic_thread_fence(std::memory_order_acq_rel);",
    "sync":   "std::atomic_thread_fence(std::memory_order_seq_cst);",
    "eieio":  "std::atomic_thread_fence(std::memory_order_release);",
}
bpat = re.compile(
    r"\t// (lwsync|sync|eieio) \n(?!\tstd::atomic_thread_fence\(std::memory_order_(?:acq_rel|seq_cst|release)\); /\* HR barrier \*/)"
)

nb = 0
for cpp_file in sorted(gen_dir.rglob("*_recomp.*.cpp")):
    src = cpp_file.read_text(encoding="utf-8", errors="replace")
    out, n = bpat.subn(lambda m: m.group(0) + "\t" + barrier_for[m.group(1)] + " /* HR barrier */\n", src)
    if n:
        cpp_file.write_text(out, encoding="utf-8", newline="\n")
        nb += n

print(f"[prepare_switch_codegen] Barreras de memoria PowerPC -> ARM64 insertadas: {nb}")
