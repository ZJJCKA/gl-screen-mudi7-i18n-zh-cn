# -*- coding: utf-8 -*-
"""Build overlay TTFs: IBM Plex Sans SC (GitHub) + device metrics (not uploaded binaries)."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fontTools import subset
from fontTools.ttLib import TTFont

from download_ibm_plex_sc import EXTRACT_DIR, find_hinted_root
from repo_paths import (
    FONT_STEMS,
    METRICS_JSON,
    OVERLAY_TTF_DIR,
    SOURCES_ZH_CN,
    load_extra_glyphs,
    overlay_font_filename,
)

EXTRA_DYNAMIC_TEXT = "中国移动中国联通中国电信中国广电"

IBM_MAP: dict[str, str] = {
    "default_medium": "IBMPlexSansSC-Medium.ttf",
    "default_semibold": "IBMPlexSansSC-SemiBold.ttf",
    "default_bold": "IBMPlexSansSC-Bold.ttf",
    "default_mono_medium": "IBMPlexSansSC-Medium.ttf",
    "default_cn_medium": "IBMPlexSansSC-Medium.ttf",
}


def load_metrics() -> dict[str, dict[str, int]]:
    data = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def apply_metrics(target: Path, metrics: dict[str, int]) -> None:
    f = TTFont(target)
    h = f["hhea"]
    h.ascent = metrics["ascent"]
    h.descent = metrics["descent"]
    h.lineGap = metrics["lineGap"]
    if "OS/2" in f:
        o = f["OS/2"]
        for key in (
            "sTypoAscender",
            "sTypoDescender",
            "sTypoLineGap",
            "usWinAscent",
            "usWinDescent",
        ):
            if key in metrics:
                setattr(o, key, metrics[key])
    f.save(target)


def repair_unicode_cmap(font: TTFont, codepoints: set[int]) -> None:
    """Expose encoded glyphs missing only from the font's Unicode cmap."""
    unicode_cmap = font.getBestCmap() or {}
    missing = codepoints.difference(unicode_cmap)
    if not missing:
        return

    all_tables = [table for table in font["cmap"].tables if hasattr(table, "cmap")]
    unicode_tables = [table for table in all_tables if table.isUnicode()]
    unresolved: list[int] = []

    for codepoint in sorted(missing):
        glyph_name = next(
            (table.cmap[codepoint] for table in all_tables if codepoint in table.cmap),
            None,
        )
        if glyph_name is None:
            unresolved.append(codepoint)
            continue
        for table in unicode_tables:
            table.cmap[codepoint] = glyph_name

    if unresolved:
        values = ", ".join(f"U+{codepoint:04X}" for codepoint in unresolved)
        raise ValueError(f"IBM Plex Sans SC lacks required glyphs: {values}")


def subset_ui_glyphs(target: Path) -> int:
    """Keep UI, carrier, high-frequency and explicitly allowed SSID glyphs."""
    text = (
        SOURCES_ZH_CN.read_text(encoding="utf-8")
        + EXTRA_DYNAMIC_TEXT
        + load_extra_glyphs()
    )
    codepoints = {ord(character) for character in text if ord(character) >= 0x20}

    options = subset.Options()
    # The UI uses only Chinese and directly mapped Latin characters. Keeping
    # every OpenType layout feature pulls hundreds of unreachable alternate
    # glyphs into the subset and nearly doubles the installed font.
    options.layout_features = []
    options.name_IDs = [1, 2, 4, 6]
    options.name_legacy = False
    options.name_languages = [0x409]
    # gl_screen renders horizontal labels and does not use OpenType shaping.
    # Dropping vertical metrics and layout tables reduces parsing and I/O while
    # retaining TrueType hinting for crisp text on the small display.
    options.drop_tables += [
        "BASE",
        "DSIG",
        "GDEF",
        "GPOS",
        "GSUB",
        "JSTF",
        "meta",
        "vhea",
        "vmtx",
    ]

    font = TTFont(target)
    repair_unicode_cmap(font, codepoints)
    worker = subset.Subsetter(options=options)
    worker.populate(unicodes=codepoints)
    worker.subset(font)
    font.save(target)
    font.close()
    return len(codepoints)


def resolve_hinted_dir(ibm_root: Path | None) -> Path:
    if ibm_root and ibm_root.is_dir():
        return find_hinted_root(ibm_root)
    if not EXTRACT_DIR.is_dir():
        raise SystemExit("Run: python scripts/download_ibm_plex_sc.py")
    roots = [p for p in EXTRACT_DIR.iterdir() if p.is_dir()]
    base = roots[0] if len(roots) == 1 else EXTRACT_DIR
    return find_hinted_root(base)


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--ibm-root", type=Path, default=None)
    args = p.parse_args()

    metrics_all = load_metrics()
    hinted = resolve_hinted_dir(args.ibm_root)
    OVERLAY_TTF_DIR.mkdir(parents=True, exist_ok=True)

    for old in OVERLAY_TTF_DIR.glob("*.ttf"):
        old.unlink()

    report: list[str] = []
    for stem in FONT_STEMS:
        ibm_name = IBM_MAP[stem]
        out_name = overlay_font_filename(stem)
        src = hinted / ibm_name
        if not src.is_file():
            raise SystemExit(f"Missing IBM font: {src}")
        if stem not in metrics_all:
            raise SystemExit(f"Missing metrics: {stem}")
        dst = OVERLAY_TTF_DIR / out_name
        shutil.copy2(src, dst)
        apply_metrics(dst, metrics_all[stem])
        glyph_count = subset_ui_glyphs(dst)
        m = metrics_all[stem]
        report.append(
            f"{out_name} <- {ibm_name} (metrics:{stem} "
            f"lh={m['ascent'] - m['descent'] + m['lineGap']}; "
            f"UI subset:{glyph_count} codepoints)"
        )

    lic_src: Path | None = None
    for cand in [hinted, *hinted.parents]:
        c = cand / "LICENSE.txt"
        if c.is_file():
            lic_src = c
            break
    if lic_src:
        shutil.copy2(lic_src, OVERLAY_TTF_DIR / "license.txt")

    (OVERLAY_TTF_DIR / "README.txt").write_text(
        "Generated by scripts/build_overlay_fonts.py (CI/local).\n"
        "Glyphs: IBM Plex Sans SC from https://github.com/IBM/plex/releases\n"
        "Modified: device metrics + performance-optimized shared glyph subset.\n"
        "Scope: translated UI, carriers, 3500 high-frequency characters and SSID allowlist.\n"
        "License: license.txt (SIL OFL 1.1)\n\n"
        + "\n".join(report)
        + "\n",
        encoding="utf-8",
    )

    print(f"Output: {OVERLAY_TTF_DIR}")
    for line in report:
        print(" ", line)


if __name__ == "__main__":
    main()
