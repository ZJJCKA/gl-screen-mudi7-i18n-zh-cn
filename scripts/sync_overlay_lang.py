# -*- coding: utf-8 -*-
"""Sync sources/zh_cn -> overlay/.../language/text/default."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from repo_paths import OVERLAY_LANG_DEFAULT, SOURCES_ZH_CN

HEADER = "// gl-screen-mudi7-i18n-zh-cn"
LEGACY_HEADERS = (
    "// gl-screen-e5800-i18n-zh-cn",
    "// gl-screen-mudi7-i18n-zh-cn",
)


def strip_project_header(body: str) -> str:
    lines = body.splitlines(keepends=True)
    if not lines:
        return body
    first = lines[0].strip()
    for header in LEGACY_HEADERS:
        if first == header or first.startswith(f"{header} build"):
            lines.pop(0)
            break
    return "".join(lines)


def main() -> None:
    if not SOURCES_ZH_CN.is_file():
        raise SystemExit(f"Missing {SOURCES_ZH_CN}")
    OVERLAY_LANG_DEFAULT.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
    body = strip_project_header(SOURCES_ZH_CN.read_text(encoding="utf-8"))
    OVERLAY_LANG_DEFAULT.write_text(
        f"{HEADER} build {stamp}\n{body}",
        encoding="utf-8",
        newline="\n",
    )
    print(f"OK -> {OVERLAY_LANG_DEFAULT}")


if __name__ == "__main__":
    main()
