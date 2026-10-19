#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hook static Switch modules ahead of ``dlopen`` in the ReXGlue SDK.

The Switch port resolves pre-linked modules through
``rex::switch_static_modules::Find()``.  This script finds the SDK module
loader / kernel resolver and inserts the lookup before every ``dlopen`` call,
guarded by ``__SWITCH__``, so statically linked modules are found before the
dynamic-loader fallback.

The patch is idempotent and always exits with status 0, including when the SDK
or a suitable loader file is absent.

Usage:
    python tools/patch_sdk_static_modules.py [SDK_PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_SDK = Path("deps/rexglue-sdk")
MARKER = "REXGLUE_STATIC_MODULES_HOOK"

PREFERRED_NAMES = (
    "module_loader.cpp",
    "moduleloader.cpp",
    "module_resolver.cpp",
    "kernel_module.cpp",
    "module.cpp",
    "kernel.cpp",
    "library.cpp",
    "library_loader.cpp",
)

DECLARATION = """\
#ifdef __SWITCH__
// %s: declare the static module table lookup.
namespace rex::switch_static_modules {
struct FunctionEntry;
extern const FunctionEntry* Find(const char* name);
}  // namespace rex::switch_static_modules
#endif
""" % MARKER


def find_loader(sdk: Path) -> Path | None:
    if not sdk.is_dir():
        return None

    cpp_files = sorted(sdk.rglob("*.cpp"), key=lambda p: (len(p.parts), str(p).lower()))

    def contains_dlopen(path: Path) -> bool:
        try:
            return "dlopen" in path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False

    for name in PREFERRED_NAMES:
        for path in cpp_files:
            if path.name.lower() == name and contains_dlopen(path):
                return path

    for path in cpp_files:
        if contains_dlopen(path):
            lowered = str(path).lower()
            try:
                text = path.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                continue
            if "module" in lowered or "module" in text or "dlopen" in text:
                return path
    return None


def first_argument(text: str, open_paren: int) -> str:
    """Return the first argument of the call whose '(' is at ``open_paren``."""
    depth = 0
    in_string: str | None = None
    escaped = False
    start = open_paren + 1

    for index in range(open_paren, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            continue
        if char in ('"', "'"):
            in_string = char
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start:index].split(",", 1)[0].strip()
        elif char == "," and depth == 1:
            return text[start:index].strip()
    return "name"


def insertion_after_includes(text: str) -> int:
    position = 0
    for match in re.finditer(r"^[ \t]*#\s*include\b.*$", text, re.MULTILINE):
        if match.start() > 8000:  # stop scanning once the file body starts
            break
        position = match.end()
    if position == 0:
        return 0
    return position + (1 if text[position:position + 1] == "\n" else 0)


def hook_block(indent: str, argument: str) -> str:
    return "\n".join(
        [
            f"{indent}#ifdef __SWITCH__",
            f"{indent}{{",
            f"{indent}  // {MARKER}: resolve statically linked modules first.",
            f"{indent}  const char* rex_static_module_name = {argument};",
            f"{indent}  if (const auto* rex_static_entry =",
            f"{indent}          ::rex::switch_static_modules::Find(rex_static_module_name)) {{",
            f"{indent}    return reinterpret_cast<void*>(",
            f"{indent}        const_cast<::rex::switch_static_modules::FunctionEntry*>(",
            f"{indent}            rex_static_entry));",
            f"{indent}  }}",
            f"{indent}}}",
            f"{indent}#endif",
            "",
        ]
    )


def patch_text(text: str) -> tuple[str, int]:
    """Insert static-module hooks before each dlopen call."""
    positions = [m.start() for m in re.finditer(r"\bdlopen\s*\(", text)]
    if not positions:
        return text, 0

    hooks: list[tuple[int, str, str]] = []
    for match in re.finditer(r"\bdlopen\s*\(", text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.start())
        if line_end == -1:
            line_end = len(text)
        line = text[line_start:line_end]
        indent = line[: len(line) - len(line.lstrip())]
        argument = first_argument(text, match.end() - 1)
        if not argument:
            argument = "name"
        hooks.append((line_start, indent, argument))

    # Build backwards so offsets stay valid.
    patched = text
    declarations_added = False
    inserted = 0
    for line_start, indent, argument in reversed(hooks):
        patched = patched[:line_start] + hook_block(indent, argument) + patched[line_start:]
        inserted += 1

    if "rex::switch_static_modules::Find" not in text:
        decl_pos = insertion_after_includes(patched)
        patched = patched[:decl_pos] + DECLARATION + "\n" + patched[decl_pos:]
        declarations_added = True

    if inserted and not declarations_added and MARKER not in text:
        # Declaration was already present; nothing else required.
        pass

    return patched, inserted


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

    target = find_loader(sdk)
    if target is None:
        print(f"[skip] No module loader with dlopen() found under {sdk}")
        return 0

    try:
        original = target.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[skip] Cannot read {target}: {exc}")
        return 0

    if MARKER in original:
        print(f"[ok] Already patched: {target}")
        return 0

    patched, hooks = patch_text(original)
    if hooks == 0:
        print(f"[ok] No dlopen() call found in {target}; no change needed")
        return 0

    backup = target.with_suffix(target.suffix + ".bak")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    target.write_text(patched, encoding="utf-8")
    print(f"[patched] {target}: static module lookup hooked before {hooks} dlopen() call(s)")
    print(f"[backup] {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
