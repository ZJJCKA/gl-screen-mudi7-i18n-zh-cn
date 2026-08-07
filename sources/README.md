# Language sources

| File | Purpose |
|------|---------|
| `en` | English UI strings (same key layout as on-device `language/text/default`) |
| `zh_cn` | Simplified Chinese translations |

See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) for trademark and licensing notes.

Do not commit router-specific secrets (passwords, tokens, serial numbers) into these files.

In `zh_cn`, the `//font` block must reference overlay basenames **`default_*_tutu_zh-cn`** (no `.ttf` suffix). CI builds the matching `*_tutu_zh-cn.ttf` files from IBM Plex Sans SC.
