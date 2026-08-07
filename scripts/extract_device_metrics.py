# -*- coding: utf-8 -*-
"""Export config/device-font-metrics.json from stock device TTF files (local tool)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fontTools.ttLib import TTFont

from repo_paths import ASSETS_DEVICE_ORIGINAL, REPO_ROOT

OUT = REPO_ROOT / "config" / "device-font-metrics.json"
KEYS = (
    "default_medium.ttf",
    "default_semibold.ttf",
    "default_bold.ttf",
    "default_mono_medium.ttf",
    "default_cn_medium.ttf",
)


def metrics_from_ttf(path: Path) -> dict[str, int]:
    f = TTFont(path)
    h = f["hhea"]
    m: dict[str, int] = {
        "ascent": int(h.ascent),
        "descent": int(h.descent),
        "lineGap": int(h.lineGap),
    }
    if "OS/2" in f:
        o = f["OS/2"]
        for key in (
            "sTypoAscender",
            "sTypoDescender",
            "sTypoLineGap",
            "usWinAscent",
            "usWinDescent",
        ):
            if hasattr(o, key):
                m[key] = int(getattr(o, key))
    return m


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument(
        "device_font_dir",
        type=Path,
        nargs="?",
        default=ASSETS_DEVICE_ORIGINAL,
        help="Directory with stock default_*.ttf from the router",
    )
    args = p.parse_args()
    if not args.device_font_dir.is_dir():
        raise SystemExit(f"Directory not found: {args.device_font_dir}")

    out: dict[str, object] = {
        "_comment": "Vertical metrics from stock GL.iNet Mudi7 language/ttf (see THIRD_PARTY_NOTICES.md)",
    }
    for name in KEYS:
        fp = args.device_font_dir / name
        if not fp.is_file():
            raise SystemExit(f"Missing: {fp}")
        key = name.removesuffix(".ttf")
        out[key] = metrics_from_ttf(fp)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
