#!/usr/bin/env python3
"""Exercise package install/remove hooks against isolated Mudi7 fixtures."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "package" / "scripts"


def shell_path(path: Path) -> str:
    return path.resolve().as_posix()


def run_hook(shell: Path, name: str, action: str, env: dict[str, str]) -> None:
    result = subprocess.run(
        [str(shell), shell_path(HOOKS / name), action],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        print(result.stdout)
        print(result.stderr)
        subprocess.run(
            [str(shell), "-x", shell_path(HOOKS / name), action],
            check=False,
            env=env,
        )
        raise RuntimeError(f"{name} failed with exit code {result.returncode}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shell", type=Path, required=True)
    args = parser.parse_args()
    if not args.shell.is_file():
        raise SystemExit(f"shell not found: {args.shell}")

    with tempfile.TemporaryDirectory(prefix="mudi7-hooks-") as temp_name:
        root = Path(temp_name)
        shim_dir = root / "test-bin"
        shim_dir.mkdir()
        chmod_shim = shim_dir / "chmod"
        chmod_shim.write_text("#!/bin/sh\nexit 0\n", encoding="ascii", newline="\n")
        chmod_shim.chmod(0o755)
        dd_shim = shim_dir / "dd"
        dd_shim.write_text(
            """#!/bin/sh
input=
output=
seek=0
skip=0
count=
for arg in "$@"; do
    case "$arg" in
        if=*) input=${arg#if=} ;;
        of=*) output=${arg#of=} ;;
        seek=*) seek=${arg#seek=} ;;
        skip=*) skip=${arg#skip=} ;;
        count=*) count=${arg#count=} ;;
    esac
done
[ -n "$input" ] || exit 1
if [ -z "$output" ]; then
    [ -n "$count" ] || exit 1
    tail -c "+$((skip + 1))" "$input" | head -c "$count"
    exit $?
fi
size=$(wc -c < "$input" | tr -d ' ')
prefix="${output}.dd-prefix.$$"
suffix="${output}.dd-suffix.$$"
new="${output}.dd-new.$$"
head -c "$seek" "$output" > "$prefix" || exit 1
tail -c "+$((seek + size + 1))" "$output" > "$suffix" || exit 1
cat "$prefix" "$input" "$suffix" > "$new" || exit 1
mv "$new" "$output" || exit 1
rm -f "$prefix" "$suffix"
exit 0
""",
            encoding="ascii",
            newline="\n",
        )
        dd_shim.chmod(0o755)
        strings_shim = shim_dir / "strings"
        strings_shim.write_text(
            "#!/bin/sh\nprintf '%s\\n' '19 Go To Ethernet Ports'\n",
            encoding="ascii",
            newline="\n",
        )
        strings_shim.chmod(0o755)
        text = root / "language" / "text" / "default"
        source = root / "language" / "text" / "default.mudi7-zh-cn"
        layout = root / "config" / "reference" / "dpr" / "layout"
        binary = root / "usr" / "bin" / "gl_screen"
        text_backup = root / "state" / "default.orig"
        style2_state = root / "state" / "style2.orig"
        binary_backup = root / "state" / "gl_screen.orig"
        for path in (text, source, layout, binary, text_backup, style2_state, binary_backup):
            path.parent.mkdir(parents=True, exist_ok=True)

        stock_text = b'WEEK_WEDNESDAY_ABBR "Wed"\nMONTH_AUGUST_ABBR "Aug"\n'
        chinese_text = (
            'WEEK_WEDNESDAY_ABBR "周三"\n'
            'MONTH_AUGUST_ABBR "8月"\n'
            'LOCK_SCREEN_DATA_STYLE1_DAY_LABEL_FORMAT "%s%d日"\n'
        ).encode("utf-8")
        stock_layout = (
            b'BEFORE 1\n'
            b'LOCK_SCREEN_DATA_STYLE2_DAY_LABEL_FORMAT "%s %d, "\n'
            b'AFTER 1\n'
        )
        stock_binary = b"\x7fELFfixture-before\x00Go To Ethernet Ports\x00fixture-after"

        text.write_bytes(stock_text)
        source.write_bytes(chinese_text)
        layout.write_bytes(stock_layout)
        binary.write_bytes(stock_binary)
        binary.chmod(0o755)

        env = os.environ.copy()
        env["PATH"] = os.pathsep.join(
            (str(shim_dir), str(args.shell.resolve().parent), env.get("PATH", ""))
        )
        env.update(
            {
                "GL_SCREEN_TEXT": shell_path(text),
                "GL_SCREEN_TEXT_SOURCE": shell_path(source),
                "GL_SCREEN_TEXT_BACKUP": shell_path(text_backup),
                "STYLE2_LAYOUT": shell_path(layout),
                "STYLE2_STATE": shell_path(style2_state),
                "GL_SCREEN_BIN": shell_path(binary),
                "GL_SCREEN_BIN_BACKUP": shell_path(binary_backup),
            }
        )

        run_hook(args.shell, "preinst", "install", env)
        run_hook(args.shell, "postinst", "configure", env)

        patched_binary = binary.read_bytes()
        assert text.read_bytes() == chinese_text
        assert b'LOCK_SCREEN_DATA_STYLE2_DAY_LABEL_FORMAT "%s%d\xe6\x97\xa5 "' in layout.read_bytes()
        assert b"Go To Ethernet Ports" not in patched_binary
        assert "以太网端口".encode("utf-8") + b"\0" * 5 in patched_binary
        assert len(patched_binary) == len(stock_binary)
        assert text_backup.read_bytes() == stock_text
        assert binary_backup.read_bytes() == stock_binary
        assert style2_state.read_bytes() == b'LOCK_SCREEN_DATA_STYLE2_DAY_LABEL_FORMAT "%s %d, "\n'

        run_hook(args.shell, "postrm", "remove", env)
        assert text.read_bytes() == stock_text
        assert layout.read_bytes() == stock_layout
        assert binary.read_bytes() == stock_binary
        assert not text_backup.exists()
        assert not style2_state.exists()
        assert not binary_backup.exists()

    print("OK: install localized both date styles and Ethernet label")
    print("OK: remove restored the original text, layout and gl_screen binary")


if __name__ == "__main__":
    main()
