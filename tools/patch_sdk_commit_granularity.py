#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch the ReXGlue SDK so Switch code-memory commits use 256 KiB chunks.

Horizon OS ``svcMapProcessCodeMemory`` fails with Kernel Resource Limit
``0xCE01`` (2001-0103) when the SDK maps code memory in 4 KiB pages.  This
script rewrites page-size constants used around the code-memory mapping calls
to 256 KiB (``256 * 1024`` / ``0x40000``).

The patch is idempotent: it is skipped when the marker is already present, and
the script exits with status 0 even when the SDK is missing or no change is
needed.

Usage:
    python tools/patch_sdk_commit_granularity.py [SDK_PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_SDK = Path("deps/rexglue-sdk")
MARKER = "REXGLUE_COMMIT_GRANULARITY_256K"

# Constants that represent a 4 KiB page and their 256 KiB replacement.
SMALL_PAGE_RE = re.compile(r"\b(0x1000(?:[uU][lL]{0,2})?|4096(?:[uU][lL]{0,2})?)\b")
SMALL_PAGE_REPLACEMENT = "0x40000 /* 256 KiB */"

# Lines mentioning these words are considered part of the mapping/commit path.
CONTEXT_WORDS = (
    "page",
    "granule",
    "granularity",
    "chunk",
    "commit",
    "align",
    "map",
    "code_memory",
    "code memory",
    "codesize",
    "code_size",
)

MAPPING_CALLS = (
    "svcMapProcessCodeMemory",
    "MapProcessCodeMemory",
    "map_process_code_memory",
    "svcUnmapProcessCodeMemory",
)


def find_sdk_file(sdk: Path) -> Path | None:
    """Return the first memory_switch.cpp / memory.cpp found in the SDK."""
    if not sdk.is_dir():
        return None

    for name in ("memory_switch.cpp", "memory.cpp"):
        matches = sorted(
            (p for p in sdk.rglob(name) if p.is_file()),
            key=lambda p: (len(p.parts), str(p).lower()),
        )
        if matches:
            return matches[0]

    # Fallback: any C++ source that maps process code memory.
    for path in sorted(sdk.rglob("*.cpp")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(call in text for call in MAPPING_CALLS):
            return path
    return None


def mapping_windows(text: str) -> list[tuple[int, int]]:
    """Return character windows around each code-memory mapping call."""
    windows: list[tuple[int, int]] = []
    for call in MAPPING_CALLS:
        for match in re.finditer(re.escape(call), text):
            windows.append((max(0, match.start() - 4000), min(len(text), match.end() + 4000)))
    return windows


def line_overlaps(start: int, end: int, windows: list[tuple[int, int]]) -> bool:
    return any(start < w_end and end > w_start for w_start, w_end in windows)


def patch_text(text: str) -> tuple[str, int]:
    """Replace 4 KiB page constants near mapping calls. Returns (text, edits)."""
    windows = mapping_windows(text)
    if not windows:
        return text, 0

    output: list[str] = []
    edits = 0
    offset = 0

    for line in text.splitlines(keepends=True):
        line_start = offset
        line_end = offset + len(line)
        offset = line_end

        if not line_overlaps(line_start, line_end, windows):
            output.append(line)
            continue

        lowered = line.lower()
        if not any(word in lowered for word in CONTEXT_WORDS):
            output.append(line)
            continue

        new_line, count = SMALL_PAGE_RE.subn(SMALL_PAGE_REPLACEMENT, line)
        output.append(new_line)
        edits += count

    return "".join(output), edits


def build_marker() -> str:
    return (
        "\n\n"
        f"// {MARKER}: Switch code-memory commits use 256 KiB chunks.\n"
        "// Horizon OS rejects 4 KiB svcMapProcessCodeMemory mappings with\n"
        "// Kernel Resource Limit 0xCE01 (2001-0103).\n"
    )


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

    target = find_sdk_file(sdk)
    if target is None:
        print(f"[skip] No memory_switch.cpp / memory.cpp found under {sdk}")
        return 0

    try:
        original = target.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[skip] Cannot read {target}: {exc}")
        return 0

    if MARKER in original:
        print(f"[ok] Already patched: {target}")
        return 0

    patched, edits = patch_text(original)
    if edits == 0:
        print(f"[ok] No 4 KiB commit granularity found in {target}; no change needed")
        return 0

    backup = target.with_suffix(target.suffix + ".bak")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    target.write_text(patched + build_marker(), encoding="utf-8")
    print(f"[patched] {target}: {edits} page-size constant(s) -> 256 KiB")
    print(f"[backup] {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
