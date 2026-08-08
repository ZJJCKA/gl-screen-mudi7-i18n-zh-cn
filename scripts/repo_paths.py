# -*- coding: utf-8 -*-
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = REPO_ROOT / "sources"
OVERLAY_DIR = REPO_ROOT / "overlay"
DIST_DIR = REPO_ROOT / "dist"
PACKAGE_SCRIPTS_DIR = REPO_ROOT / "package" / "scripts"
ASSETS_DIR = REPO_ROOT / "assets"

SOURCES_EN = SOURCES_DIR / "en"
SOURCES_ZH_CN = SOURCES_DIR / "zh_cn"
OVERLAY_LANG_DEFAULT = OVERLAY_DIR / "etc" / "gl_screen" / "language" / "text" / "default"
OVERLAY_TTF_DIR = OVERLAY_DIR / "etc" / "gl_screen" / "language" / "ttf"
METRICS_JSON = REPO_ROOT / "config" / "device-font-metrics.json"
EXTRA_GLYPHS_TXT = REPO_ROOT / "config" / "extra-glyphs.txt"

ASSETS_IBM_CACHE = ASSETS_DIR / "cache" / "ibm-plex-sans-sc"
ASSETS_DEVICE_ORIGINAL = ASSETS_DIR / "device-original-ttf"

# Overlay TTF: IBM Plex Sans SC (downloaded in CI) + metrics from config/
FONT_OVERLAY_SUFFIX = "_tutu_zh-cn.ttf"

FONT_STEMS = (
    "default_medium",
)


def load_extra_glyphs() -> str:
    if not EXTRA_GLYPHS_TXT.is_file():
        raise FileNotFoundError(f"Missing extra glyph allowlist: {EXTRA_GLYPHS_TXT}")
    text = "".join(
        line.strip()
        for line in EXTRA_GLYPHS_TXT.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    cjk = {character for character in text if "\u3400" <= character <= "\u9fff"}
    if len(cjk) < 3500:
        raise ValueError(
            f"Extra glyph allowlist must contain at least 3500 unique CJK characters; got {len(cjk)}"
        )
    return text


def overlay_font_filename(stem: str) -> str:
    return f"{stem}{FONT_OVERLAY_SUFFIX}"


def overlay_font_basename(stem: str) -> str:
    return overlay_font_filename(stem)[:-4]


# Stock GL screen UI package on the tested GL.iNet Mudi7 firmware (opkg Depends)
DEPENDS_GL_SCREEN_SDK = "gl-sdk4-screen-large (= git-2026.142.39025-c3b9432-1)"
