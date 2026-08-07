# -*- coding: utf-8 -*-
"""CI/local: download IBM fonts, build overlay TTFs, sync language file."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def run(script: str) -> None:
    print(f"\n=== {script} ===")
    subprocess.run([sys.executable, str(SCRIPTS / script)], check=True)


def main() -> None:
    run("download_ibm_plex_sc.py")
    run("build_overlay_fonts.py")
    run("sync_overlay_lang.py")
    print("\nOK: overlay ready")


if __name__ == "__main__":
    main()
