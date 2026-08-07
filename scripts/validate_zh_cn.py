# -*- coding: utf-8 -*-
"""校验 zh_cn 与 en：行数/键名一致，且每行格式为 KEY "value" 单行。"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

KEY_RE = re.compile(r'^([A-Za-z0-9_@]+)\s+(.+)$')


def parse_logical_lines(path: Path) -> list[tuple[int, str, str | None, str | None]]:
    """返回 (物理行号, 原始行, key, value_or_ref)。"""
    text = path.read_text(encoding="utf-8")
    physical = text.splitlines()
    logical = []
    i = 0
    while i < len(physical):
        start = i + 1
        line = physical[i]
        if not line.strip() or line.startswith("//"):
            logical.append((start, line, None, None))
            i += 1
            continue
        m = KEY_RE.match(line)
        if not m:
            logical.append((start, line, "__BAD__", None))
            i += 1
            continue
        key, rest = m.group(1), m.group(2)
        if rest.startswith('"'):
            buf = [line]
            combined = line
            while not _quoted_value_complete(combined) and i + 1 < len(physical):
                i += 1
                combined += "\n" + physical[i]
                buf.append(physical[i])
            logical.append((start, "\n".join(buf), key, rest))
            i += 1
            continue
        logical.append((start, line, key, rest))
        i += 1
    return logical


def _quoted_value_complete(line: str) -> bool:
    """判断 KEY "..." 形式的引号是否在同一物理行内闭合（简化）。"""
    rest = line.split(None, 1)[1] if len(line.split(None, 1)) == 2 else line
    if rest == '"""' or (
        len(rest) == 3 and rest[0] == '"' and rest[1] == "\\" and rest[2] == '"'
    ):
        return True
    idx = line.find('"')
    if idx < 0:
        return True
    i = idx + 1
    while i < len(line):
        if line[i] == "\\":
            i += 2
            continue
        if line[i] == '"':
            tail = line[i + 1 :].strip()
            return tail == "" or tail.startswith("//")
        i += 1
    return False


def extract_key_only(line: str) -> str | None:
    s = line.strip()
    if not s or s.startswith("//"):
        return None
    m = KEY_RE.match(s)
    return m.group(1) if m else "__BAD__"


def main() -> None:
    from repo_paths import PACKAGE_SCRIPTS_DIR, SOURCES_EN, SOURCES_ZH_CN

    en_path = SOURCES_EN
    zh_path = SOURCES_ZH_CN
    en_lines = en_path.read_text(encoding="utf-8").splitlines()
    zh_lines = zh_path.read_text(encoding="utf-8").splitlines()

    print(f"物理行数: en={len(en_lines)}, zh_cn={len(zh_lines)}")
    has_error = False

    expected_date_lines = {
        'LOCK_SCREEN_DATA_STYLE1_DAY_LABEL_FORMAT "%s%d日"',
        'WEEK_SUNDAY_ABBR "周日"',
        'WEEK_MONDAY_ABBR "周一"',
        'WEEK_TUESDAY_ABBR "周二"',
        'WEEK_WEDNESDAY_ABBR "周三"',
        'WEEK_THURSDAY_ABBR "周四"',
        'WEEK_FRIDAY_ABBR "周五"',
        'WEEK_SATURDAY_ABBR "周六"',
        'WEEK_SUNDAY_ABBR_LOWER "周日"',
        'WEEK_MONDAY_ABBR_LOWER "周一"',
        'WEEK_TUESDAY_ABBR_LOWER "周二"',
        'WEEK_WEDNESDAY_ABBR_LOWER "周三"',
        'WEEK_THURSDAY_ABBR_LOWER "周四"',
        'WEEK_FRIDAY_ABBR_LOWER "周五"',
        'WEEK_SATURDAY_ABBR_LOWER "周六"',
        *{f'MONTH_{month}_ABBR "{number}月"' for number, month in enumerate((
            "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
            "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
        ), 1)},
    }
    missing_date_lines = sorted(expected_date_lines.difference(zh_lines))
    if missing_date_lines:
        print("ERROR: date localization entries are missing or have unexpected values:")
        for line in missing_date_lines:
            print(" ", line)
        has_error = True
    else:
        print("OK: date localization is complete (example: 8月7日 / 周三)")

    expected_style_lines = {
        'WAKE_DISPLAY_STYLE_1_OPTION_LABEL_TEXT "主题一"',
        'WAKE_DISPLAY_STYLE_2_OPTION_LABEL_TEXT "主题二"',
    }
    missing_style_lines = sorted(expected_style_lines.difference(zh_lines))
    if missing_style_lines:
        print("ERROR: wake display style labels are not localized:")
        for line in missing_style_lines:
            print(" ", line)
        has_error = True
    else:
        print("OK: wake display style labels are 主题一 / 主题二")

    postinst_text = (PACKAGE_SCRIPTS_DIR / "postinst").read_text(encoding="utf-8")
    style2_marker = "%%s%%d\\346\\227\\245"
    if style2_marker not in postinst_text:
        print("ERROR: lock-screen style 2 date format is not localized")
        has_error = True
    else:
        print("OK: lock-screen style 2 date format is complete (example: 8月7日 周三)")

    required_postinst_markers = {
        "default.mudi7-zh-cn": "Mudi7 language payload path",
        "Go To Ethernet Ports": "stock hard-coded Ethernet label",
        "以太网端口": "Chinese Ethernet label",
    }
    for marker, description in required_postinst_markers.items():
        if marker not in postinst_text:
            print(f"ERROR: postinst is missing {description}: {marker}")
            has_error = True
    if not any(marker not in postinst_text for marker in required_postinst_markers):
        print("OK: hard-coded Go To Ethernet Ports label will become 以太网端口")
    if "grep -a -b" in postinst_text or "grep -a -q" in postinst_text:
        print("ERROR: postinst still relies on GNU grep binary/byte-offset options")
        has_error = True
    else:
        print("OK: Ethernet patch does not rely on unsupported BusyBox grep options")

    en_keys = [extract_key_only(l) for l in en_lines]
    zh_keys = [extract_key_only(l) for l in zh_lines]

    # 检测 zh 中跨行字符串（物理行数多于 en）
    multiline_issues = []
    for i, line in enumerate(zh_lines, 1):
        if not line.strip() or line.startswith("//"):
            continue
        m = KEY_RE.match(line)
        if m and m.group(2).startswith('"') and not _quoted_value_complete(line):
            multiline_issues.append(i)

    print(f"zh_cn 未闭合引号/跨行条目起始行: {len(multiline_issues)}")
    if multiline_issues:
        print("  示例:", multiline_issues[:15])

    # 按 en 的键序列对齐（仅非注释行）
    def key_sequence(keys):
        return [k for k in keys if k is not None]

    en_seq = key_sequence(en_keys)
    zh_seq = key_sequence(zh_keys)

    print(f"逻辑条目数(有键): en={len(en_seq)}, zh_cn={len(zh_seq)}")

    if len(en_seq) != len(zh_seq):
        print("ERROR: 逻辑条目数量不一致")
        has_error = True
    else:
        mismatches = []
        for n, (ek, zk) in enumerate(zip(en_seq, zh_seq), 1):
            if ek != zk:
                mismatches.append((n, ek, zk))
        if mismatches:
            print(f"ERROR: 键名不一致 {len(mismatches)} 处")
            for item in mismatches[:20]:
                print(" ", item)
            has_error = True
        else:
            print("OK: 所有键名与 en 顺序一致")

    if len(en_lines) != len(zh_lines):
        print(f"ERROR: 物理行数不一致，差 {len(zh_lines) - len(en_lines)} 行（多为 \\n 被写成真实换行）")
        has_error = True
    elif multiline_issues:
        print("ERROR: zh_cn 存在未闭合引号/跨行条目")
        has_error = True
    elif not multiline_issues:
        print("OK: 物理行数一致且无跨行引号")

    if has_error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
