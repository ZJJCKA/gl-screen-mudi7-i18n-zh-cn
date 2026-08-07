# -*- coding: utf-8 -*-
"""Download IBM Plex Sans SC release zip (hinted TTF). Used by CI and local build."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from repo_paths import ASSETS_IBM_CACHE

DEFAULT_RELEASE_TAG = "@ibm/plex-sans-sc@1.1.0"
DEFAULT_ZIP_NAME = "ibm-plex-sans-sc.zip"
EXTRACT_DIR = ASSETS_IBM_CACHE / "extracted"


def release_zip_url(tag: str, zip_name: str) -> str:
    enc_tag = urllib.request.quote(tag, safe="")
    return f"https://github.com/IBM/plex/releases/download/{enc_tag}/{zip_name}"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=600) as resp:
        dest.write_bytes(resp.read())
    print(f"  -> {dest} ({dest.stat().st_size} bytes)")


def extract_zip(zip_path: Path, out_dir: Path) -> Path:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)
    roots = [p for p in out_dir.iterdir() if p.is_dir()]
    return roots[0] if len(roots) == 1 else out_dir


def find_hinted_root(extracted: Path) -> Path:
    hinted = extracted / "fonts" / "complete" / "ttf" / "hinted"
    if hinted.is_dir():
        return hinted
    matches = list(extracted.rglob("fonts/complete/ttf/hinted"))
    if matches:
        return matches[0]
    raise SystemExit(f"Hinted TTF dir not found under {extracted}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tag", default=DEFAULT_RELEASE_TAG)
    p.add_argument("--zip-name", default=DEFAULT_ZIP_NAME)
    p.add_argument("--cache-dir", type=Path, default=ASSETS_IBM_CACHE)
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    zip_path = args.cache_dir / args.zip_name
    url = release_zip_url(args.tag, args.zip_name)

    if args.force or not zip_path.is_file():
        download(url, zip_path)
        (args.cache_dir / "meta.json").write_text(
            json.dumps({"tag": args.tag, "url": url}, indent=2),
            encoding="utf-8",
        )
    else:
        print(f"Using cached: {zip_path}")

    root = extract_zip(zip_path, EXTRACT_DIR)
    hinted = find_hinted_root(root)
    print(f"Hinted: {hinted} ({len(list(hinted.glob('*.ttf')))} TTF)")


if __name__ == "__main__":
    main()
