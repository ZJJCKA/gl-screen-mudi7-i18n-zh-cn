# -*- coding: utf-8 -*-
"""Build and verify the gzip-tar IPK format used by the Mudi7 firmware."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import re
import shutil
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent))

from repo_paths import DEPENDS_GL_SCREEN_SDK, DIST_DIR, OVERLAY_DIR, PACKAGE_SCRIPTS_DIR

ALLOWED_PREFIXES = (
    "etc/gl_screen/language/text/",
    "etc/gl_screen/language/ttf/",
)
LANG_DEFAULT_REL = Path("etc/gl_screen/language/text/default")
LANG_PACKAGE_REL = Path("etc/gl_screen/language/text/default.mudi7-zh-cn")

DEFAULT_PACKAGE = "gl-screen-mudi7-i18n-zh-cn"
DEFAULT_MAINTAINER = "ZJJCKA <514414031@qq.com>"
DEFAULT_HOMEPAGE = "https://github.com/ZJJCKA/gl-screen-mudi7-i18n-zh-cn"
DEFAULT_CONFLICTS = "gl-screen-i18n-zh-cn, gl-screen-e5800-i18n-zh-cn"
EXTRA_DYNAMIC_TEXT = "中国移动中国联通中国电信中国广电"
DEFAULT_DESCRIPTION = (
    "GL.iNet Mudi7 screen Simplified Chinese language pack.\n"
    " Installs the translated language file and one shared static-UI font subset.\n"
    " Uses the stock complete Chinese font as fallback for dynamic content.\n"
    " Localizes both lock-screen date styles, including the final day suffix.\n"
    " Localizes the hard-coded Ethernet navigation label without changing ELF size.\n"
    " Backs up every modified stock file and restores it on package removal.\n"
    " Runs /etc/init.d/gl_screen restart after install/remove.\n"
    f" Requires: {DEPENDS_GL_SCREEN_SDK}."
)


def default_version() -> str:
    return datetime.now(timezone.utc).strftime("%Y.%m.%d.%H%M%S")


def format_description_block(description: str) -> str:
    lines = [line.rstrip() for line in description.strip().splitlines()]
    if not lines:
        return "Description:\n"
    block = f"Description: {lines[0]}\n"
    for line in lines[1:]:
        block += f" {line}\n"
    return block


def iter_payload_files(overlay_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(overlay_root.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        rel = path.relative_to(overlay_root).as_posix()
        if not any(rel.startswith(prefix) for prefix in ALLOWED_PREFIXES):
            raise SystemExit(f"Refusing to pack outside language/: {rel}")
        files.append(path)
    if not files:
        raise SystemExit(f"No payload files under {overlay_root}")
    return files


def collect_control_scripts() -> list[Path]:
    if not PACKAGE_SCRIPTS_DIR.is_dir():
        return []
    order = ("preinst", "postinst", "prerm", "postrm")
    found = {
        path.name: path
        for path in PACKAGE_SCRIPTS_DIR.iterdir()
        if path.is_file() and path.suffix == "" and not path.name.startswith(".")
    }
    scripts: list[Path] = []
    for name in order:
        if name in found:
            scripts.append(found.pop(name))
    scripts.extend(sorted(found.values(), key=lambda path: path.name))
    return scripts


def write_text_lf(path: Path, text: str, mode: int) -> None:
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    path.chmod(mode)


def copy_payload(overlay_root: Path, pkg_root: Path, files: list[Path]) -> None:
    for src in files:
        rel = src.relative_to(overlay_root)
        if rel == LANG_DEFAULT_REL:
            rel = LANG_PACKAGE_REL
        dest = pkg_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        dest.chmod(0o644)


def make_control_text(
    package: str,
    version: str,
    architecture: str,
    maintainer: str,
    homepage: str,
    description: str,
    depends: str,
    installed_kb: int,
) -> str:
    return (
        f"Package: {package}\n"
        f"Version: {version}\n"
        f"Architecture: {architecture}\n"
        f"Depends: {depends}\n"
        f"Conflicts: {DEFAULT_CONFLICTS}\n"
        f"Maintainer: {maintainer}\n"
        f"Homepage: {homepage}\n"
        "Section: misc\n"
        "Priority: optional\n"
        f"Installed-Size: {installed_kb}\n"
        f"{format_description_block(description)}"
    )


def build_pkg_root(
    overlay_root: Path,
    work_dir: Path,
    package: str,
    version: str,
    architecture: str,
    maintainer: str,
    homepage: str,
    description: str,
    depends: str,
) -> tuple[Path, list[Path], list[Path]]:
    files = iter_payload_files(overlay_root)
    installed_kb = (sum(path.stat().st_size for path in files) + 1023) // 1024
    pkg_root = work_dir / f"{package}_{version}_{architecture}"
    control_dir = pkg_root / "CONTROL"
    control_dir.mkdir(parents=True)

    copy_payload(overlay_root, pkg_root, files)
    write_text_lf(
        control_dir / "control",
        make_control_text(
            package,
            version,
            architecture,
            maintainer,
            homepage,
            description,
            depends,
            installed_kb,
        ),
        0o644,
    )

    scripts = collect_control_scripts()
    for script in scripts:
        text = script.read_text(encoding="utf-8")
        write_text_lf(control_dir / script.name, text, 0o755)

    return pkg_root, files, scripts


def normalize_name(name: str) -> str:
    return name[2:] if name.startswith("./") else name


def tar_info(name: str, mode: int, epoch: int, size: int = 0) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.mode = mode
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    info.mtime = epoch
    info.size = size
    return info


def parent_directories(names: list[str]) -> set[str]:
    directories: set[str] = set()
    for name in names:
        path = PurePosixPath(normalize_name(name))
        for parent in path.parents:
            if str(parent) != ".":
                directories.add(f"./{parent.as_posix()}/")
    return directories


def make_tar_gz(
    files: dict[str, tuple[bytes, int]], directories: set[str], epoch: int
) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(
        filename="", fileobj=output, mode="wb", compresslevel=9, mtime=0
    ) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.GNU_FORMAT) as archive:
            for directory in sorted(
                directories,
                key=lambda item: (len(PurePosixPath(item).parts), item),
            ):
                name = directory if directory.endswith("/") else directory + "/"
                info = tar_info(name, 0o755, epoch)
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            for name in sorted(files):
                content, mode = files[name]
                archive.addfile(
                    tar_info(name, mode, epoch, len(content)), io.BytesIO(content)
                )
    return output.getvalue()


def collect_archive_files(root: Path) -> dict[str, tuple[bytes, int]]:
    files: dict[str, tuple[bytes, int]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        files[f"./{relative}"] = (path.read_bytes(), path.stat().st_mode & 0o777)
    return files


def make_outer_tar_ipk(control_tar: bytes, data_tar: bytes, epoch: int) -> bytes:
    """Create the gzip-wrapped outer tar expected by GL's OpenWrt 21.02 opkg."""
    output = io.BytesIO()
    with gzip.GzipFile(
        filename="", fileobj=output, mode="wb", compresslevel=9, mtime=0
    ) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.GNU_FORMAT) as archive:
            for name, content in (
                ("debian-binary", b"2.0\n"),
                ("data.tar.gz", data_tar),
                ("control.tar.gz", control_tar),
            ):
                info = tar_info(f"./{name}", 0o644, epoch, len(content))
                archive.addfile(info, io.BytesIO(content))
    return output.getvalue()


def read_tar_files(payload: bytes) -> dict[str, tuple[bytes, int]]:
    result: dict[str, tuple[bytes, int]] = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"cannot extract tar member: {member.name}")
            result[normalize_name(member.name)] = (stream.read(), member.mode)
    return result


def verify_ipk(
    ipk_path: Path,
    package: str,
    version: str,
    architecture: str,
    depends: str,
) -> str:
    payload = ipk_path.read_bytes()
    if not payload.startswith(b"\x1f\x8b"):
        raise ValueError("Mudi7 IPK outer archive must be gzip-tar format")
    outer = read_tar_files(payload)
    if list(outer) != ["debian-binary", "data.tar.gz", "control.tar.gz"]:
        raise ValueError(f"unexpected IPK members: {list(outer)}")
    if outer["debian-binary"][0] != b"2.0\n":
        raise ValueError("invalid debian-binary marker")

    control = read_tar_files(outer["control.tar.gz"][0])
    control_text = control["control"][0].decode("utf-8")
    for required in (
        f"Package: {package}",
        f"Version: {version}",
        f"Architecture: {architecture}",
        f"Depends: {depends}",
        f"Conflicts: {DEFAULT_CONFLICTS}",
    ):
        if required not in control_text:
            raise ValueError(f"missing control field: {required}")
    for script in ("preinst", "postinst", "postrm"):
        content, mode = control[script]
        if mode != 0o755:
            raise ValueError(f"wrong mode for {script}: {oct(mode)}")
        if b"\r" in content:
            raise ValueError(f"non-Unix line endings in {script}")

    data = read_tar_files(outer["data.tar.gz"][0])
    language_name = LANG_PACKAGE_REL.as_posix()
    if language_name not in data:
        raise ValueError(f"missing packaged language file: {language_name}")
    if data[language_name][1] != 0o644:
        raise ValueError("language file mode must be 0644")
    language_text = data[language_name][0].decode("utf-8")
    for expected in (
        'LOCK_SCREEN_DATA_STYLE1_DAY_LABEL_FORMAT "%s%d日"',
        'WAKE_DISPLAY_STYLE_1_OPTION_LABEL_TEXT "主题一"',
        'WAKE_DISPLAY_STYLE_2_OPTION_LABEL_TEXT "主题二"',
        'WEEK_WEDNESDAY_ABBR "周三"',
        'WEEK_WEDNESDAY_ABBR_LOWER "周三"',
        'MONTH_AUGUST_ABBR "8月"',
    ):
        if expected not in language_text.splitlines():
            raise ValueError(f"missing packaged date localization: {expected}")
    ttf_names = [name for name in data if name.endswith(".ttf")]
    if len(ttf_names) != 1:
        raise ValueError(f"expected one shared packaged font, got {len(ttf_names)}")
    for name in ttf_names:
        if data[name][1] != 0o644:
            raise ValueError(f"font mode must be 0644: {name}")
        if len(data[name][0]) > 300_000:
            raise ValueError(f"UI font was not subset: {name} ({len(data[name][0])} bytes)")

        font = TTFont(io.BytesIO(data[name][0]))
        cmap = set(font.getBestCmap() or {})
        required = {
            ord(character)
            for character in language_text + EXTRA_DYNAMIC_TEXT
            if ord(character) >= 0x20
        }
        missing = sorted(required.difference(cmap))
        if missing:
            raise ValueError(
                f"UI font lacks required glyphs: {''.join(chr(value) for value in missing[:20])}"
            )
        font.close()
    referenced_fonts = set(
        re.findall(
            r'^FONT_(?:MEDIUM|BOLD|SEMIBOLD|MONO_MEDIUM|CN_MEDIUM) "([^"]+)"$',
            language_text,
            flags=re.MULTILINE,
        )
    )
    packaged_fonts = {Path(name).stem for name in ttf_names}
    stock_fonts = {"default_cn_medium"}
    if referenced_fonts != packaged_fonts | stock_fonts:
        raise ValueError(
            f"language font references do not match packaged fonts: "
            f"refs={sorted(referenced_fonts)}, files={sorted(packaged_fonts)}, "
            f"stock={sorted(stock_fonts)}"
        )
    postinst_text = control["postinst"][0].decode("utf-8")
    for marker in ("%%s%%d\\346\\227\\245", "Go To Ethernet Ports", "以太网端口"):
        if marker not in postinst_text:
            raise ValueError(f"postinst localization marker is missing: {marker}")
    return hashlib.sha256(payload).hexdigest()


def build_ipk(
    overlay_root: Path,
    out_dir: Path,
    package: str,
    version: str,
    architecture: str,
    maintainer: str,
    homepage: str,
    description: str,
    depends: str,
    keep_pkg_root: Path | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ipk-build-") as temp_name:
        work_dir = Path(temp_name)
        pkg_root, files, scripts = build_pkg_root(
            overlay_root,
            work_dir,
            package,
            version,
            architecture,
            maintainer,
            homepage,
            description,
            depends,
        )

        if keep_pkg_root is not None:
            if keep_pkg_root.exists():
                shutil.rmtree(keep_pkg_root)
            shutil.copytree(pkg_root, keep_pkg_root)
        epoch = int(os.environ.get("SOURCE_DATE_EPOCH", str(int(datetime.now().timestamp()))))
        data_root = pkg_root
        data_files: dict[str, tuple[bytes, int]] = {}
        for name, value in collect_archive_files(data_root).items():
            if not normalize_name(name).startswith("CONTROL/"):
                data_files[name] = (value[0], 0o644)
        control_files = {
            name: (
                value[0],
                0o755 if normalize_name(name) in {"preinst", "postinst", "prerm", "postrm"} else 0o644,
            )
            for name, value in collect_archive_files(pkg_root / "CONTROL").items()
        }
        data_tar = make_tar_gz(data_files, parent_directories(list(data_files)), epoch)
        control_tar = make_tar_gz(
            control_files, parent_directories(list(control_files)), epoch
        )
        ipk_path = out_dir / f"{package}_{version}_{architecture}.ipk"
        ipk_path.write_bytes(make_outer_tar_ipk(control_tar, data_tar, epoch))

    digest = verify_ipk(ipk_path, package, version, architecture, depends)
    installed_kb = (sum(path.stat().st_size for path in files) + 1023) // 1024

    print(f"IPK: {ipk_path}")
    print(f"  sha256: {digest}")
    print(f"  version: {version}")
    print(f"  depends: {depends}")
    print(f"  control scripts: {[path.name for path in scripts] or '(none)'}")
    print(f"  files: {len(files)}, installed ~{installed_kb} KiB")
    for path in files:
        rel = path.relative_to(overlay_root).as_posix()
        print(f"    ./{rel} ({path.stat().st_size} bytes)")
    return ipk_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a verified OpenWrt IPK from overlay/")
    parser.add_argument("--overlay", type=Path, default=OVERLAY_DIR)
    parser.add_argument("--out-dir", type=Path, default=DIST_DIR)
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    parser.add_argument("--version", default=None, help="Version (default: UTC YYYY.MM.DD.HHMMSS)")
    parser.add_argument("--arch", default="all")
    parser.add_argument("--maintainer", default=DEFAULT_MAINTAINER)
    parser.add_argument("--homepage", default=DEFAULT_HOMEPAGE)
    parser.add_argument("--description", default=DEFAULT_DESCRIPTION)
    parser.add_argument("--depends", default=DEPENDS_GL_SCREEN_SDK)
    parser.add_argument("--keep-pkg-root", type=Path, default=None)
    args = parser.parse_args()

    if not args.overlay.is_dir():
        raise SystemExit(f"Missing overlay dir: {args.overlay}")

    build_ipk(
        args.overlay,
        args.out_dir,
        args.package,
        args.version or default_version(),
        args.arch,
        args.maintainer,
        args.homepage,
        args.description,
        args.depends,
        args.keep_pkg_root,
    )


if __name__ == "__main__":
    main()
