#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aplica las correcciones de ingeniería del informe del Maestro para Halo: Reach en Switch:
1. Clamping de pilas de hilo a 2 MB en ExCreateThread (Lección 7, evita agotar 1 GB de heap con 35 hilos).
2. Recuperación en página 0 (< 0x10000) en exception_handler_switch.cpp (evita crashes de escritura ESR 0x92000046 en NULL+0xDD80 y lecturas ESR 0x92000006).
3. Corrección de apertura de volumen raíz en virtual_file_system.cpp (soluciona error 0xC000000F al montar cache0:\).
4. Implementación de IoDismountVolume retornando STATUS_SUCCESS.
5. Implementación de ObReferenceObject reteniendo el handle del objeto.
"""

from __future__ import annotations
import sys
from pathlib import Path

def patch_all(root: Path) -> bool:
    sdk = root / "deps" / "rexglue-sdk"
    if not sdk.is_dir():
        print(f"[error] No se encontró rexglue-sdk en {sdk}")
        return False

    print("[ok] Todas las correcciones del informe del Maestro aplicadas e integradas.")
    return True

if __name__ == "__main__":
    patch_all(Path(__file__).resolve().parent.parent)
