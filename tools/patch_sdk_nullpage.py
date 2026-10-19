#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recover guest null-page reads in the ReXGlue Switch exception handler.

Xbox 360 games sometimes read from the guest null page (``0x00000000``).
On real hardware those reads return zero; on the Switch the ARM64 LDR faults
and the emulator crashes.  This script patches
``exception_handler_switch.cpp`` so that, for faults inside
``[guest_base, guest_base + 0x10000)``, the destination X/W register is set to
0, the PC is advanced by 4 bytes and the handler returns ``true``.

The patch is idempotent and always exits with status 0, including when the SDK
or the handler file is absent.

Usage:
    python tools/patch_sdk_nullpage.py [SDK_PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_SDK = Path("deps/rexglue-sdk")
MARKER = "REXGLUE_NULLPAGE_RECOVERY"
HANDLER_NAME = "exception_handler_switch.cpp"

FAULT_WORDS = ("fault_addr", "fault_address", "si_addr", "faultaddr")


def find_handler(sdk: Path) -> Path | None:
    if not sdk.is_dir():
        return None
    matches = sorted(
        (p for p in sdk.rglob(HANDLER_NAME) if p.is_file()),
        key=lambda p: (len(p.parts), str(p).lower()),
    )
    return matches[0] if matches else None


def detect_expression(text: str, names: tuple[str, ...], fallback: str) -> str:
    """Detect expressions such as ``ctx->x[n]`` / ``thread.pc`` near the fault code."""
    for name in names:
        pattern = re.compile(
            rf"([A-Za-z_]\w*)\s*(->|\.)\s*(?:{name})\s*\[",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            return f"{match.group(1)}{match.group(2)}{name}[{{index}}]"
    return fallback


def detect_scalar(text: str, names: tuple[str, ...], fallback: str) -> str:
    for name in names:
        pattern = re.compile(rf"([A-Za-z_]\w*)\s*(->|\.)\s*({name})\b", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return f"{match.group(1)}{match.group(2)}{match.group(3)}"
    return fallback


def detect_setter(text: str) -> str | None:
    match = re.search(
        r"([A-Za-z_]\w*)\s*(->|\.)\s*(SetX|SetRegister|SetGpr|SetReg)\s*\(",
        text,
        re.IGNORECASE,
    )
    if match:
        return f"{match.group(1)}{match.group(2)}{match.group(3)}({{index}}, 0)"
    return None


def find_return_false(text: str) -> tuple[int, str] | None:
    """Find a ``return false;`` inside a handler that mentions the fault address."""
    best: tuple[int, str] | None = None
    for match in re.finditer(r"^([ \t]*)return\s+false\s*;", text, re.MULTILINE):
        start = match.start()
        preceding = text[max(0, start - 6000):start]
        if any(word in preceding for word in FAULT_WORDS):
            # Prefer the last one in the fault-handling function.
            best = (match.start(), match.group(1))
    return best


def build_block(indent: str, text: str) -> str:
    fault = detect_scalar(text, FAULT_WORDS, "fault_addr")
    guest_base = detect_scalar(
        text, ("guest_base", "guestBase", "base_address", "image_base"), "guest_base"
    )
    reg = detect_expression(text, ("x", "X", "regs", "gpr"), "ctx->x[{index}]")
    pc = detect_scalar(text, ("pc", "PC", "Pc"), "ctx->pc")
    setter = detect_setter(text)

    def store_reg(index: str) -> str:
        if setter:
            return setter.format(index=index)
        return f"{reg.format(index=index)} = 0;"

    lines = [
        f"{indent}// {MARKER}_BEGIN",
        f"{indent}#ifdef __aarch64__",
        f"{indent}if ({fault} >= ({guest_base}) && {fault} < ({guest_base}) + 0x10000u) {{",
        f"{indent}  const uint32_t nullpage_insn =",
        f"{indent}      *reinterpret_cast<const uint32_t*>({pc});",
        f"{indent}  const uint32_t nullpage_rt = nullpage_insn & 0x1Fu;",
        f"{indent}  // LDR Xt (unsigned offset)",
        f"{indent}  if ((nullpage_insn & 0xFFC00000u) == 0xF9400000u) {{",
        f"{indent}    {store_reg('nullpage_rt')}",
        f"{indent}    {pc} += 4;",
        f"{indent}    return true;",
        f"{indent}  }}",
        f"{indent}  // LDR Wt (unsigned offset); zero-extends into Xt",
        f"{indent}  if ((nullpage_insn & 0xFFC00000u) == 0xB9400000u) {{",
        f"{indent}    {store_reg('nullpage_rt')}",
        f"{indent}    {pc} += 4;",
        f"{indent}    return true;",
        f"{indent}  }}",
        f"{indent}}}",
        f"{indent}#endif",
        f"{indent}// {MARKER}_END",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "sdk_path",
        nargs="?",
        default=str(DEFAULT_SDK),
        help=f"Path to the ReXGlue SDK (default: {DEFAULT_SDK})",
    )
    args = parser.parse_args(argv)

    sdk = Path(args.sdk_path)
    if not sdk.is_dir():
        print(f"[skip] SDK directory not found: {sdk} (nothing to patch)")
        return 0

    target = find_handler(sdk)
    if target is None:
        print(f"[skip] {HANDLER_NAME} not found under {sdk}")
        return 0

    try:
        original = target.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[skip] Cannot read {target}: {exc}")
        return 0

    if MARKER in original:
        print(f"[ok] Already patched: {target}")
        return 0

    found = find_return_false(original)
    if found is None:
        print(f"[skip] No fault handler with 'return false;' found in {target}")
        return 0

    position, indent = found
    block = build_block(indent, original)
    patched = original[:position] + block + original[position:]

    backup = target.with_suffix(target.suffix + ".bak")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    target.write_text(patched, encoding="utf-8")
    print(f"[patched] {target}: null-page LDR recovery injected")
    print(f"[backup] {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
