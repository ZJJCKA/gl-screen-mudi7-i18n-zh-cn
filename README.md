# gl-screen-mudi7-i18n-zh-cn

GL.iNet Mudi7 (`glinet-mudi7`) 屏幕界面简体中文 OpenWrt 安装包。

本项目以用户提供的 Mudi7 原版英文资源为基准，英文与中文词典均为 825 个键，顺序完全一致。安装包包含中文词典和一份共享完整中文字库；中文专用角色复用设备原装 `default_cn_medium.ttf`，避免重复打包五份大字体。另处理词典以外的两个显示点：

- 锁屏日期样式 1：`8月7日`，星期显示为 `周三`。
- 锁屏日期样式 2：把原版 `%s %d, ` 改为 `%s%d日 `，保证不缺最后的“日”字。
- 唤醒显示样式：`Style1`、`Style2` 改为“主题一”、“主题二”。
- 以太网页面的硬编码按钮：`Go To Ethernet Ports` 改为 `以太网端口`。

安装前会备份原版词典、日期布局行和 `/usr/bin/gl_screen`；卸载时逐项还原。二进制按钮汉化保持原字符串占用的 20 字节不变，若设备二进制中找不到精确英文标记则安全跳过，不会盲目修改。

## 本地构建

```sh
cd gl-screen-mudi7-i18n-zh-cn
pip install -r requirements.txt
python scripts/prepare_overlay.py
python scripts/validate_zh_cn.py
python scripts/build_ipk.py --version 2026.08.07.6
```

输出文件：

```text
dist/gl-screen-mudi7-i18n-zh-cn_2026.08.07.6_all.ipk
```

构建器直接生成 Mudi7/OpenWrt 21.02 使用的 gzip-tar 外层 IPK，并检查外层成员、控制脚本权限、Unix 换行、词典与字体权限，避免生成 `Malformed package file`。

## 安装

依赖设备固件中的：

```text
gl-sdk4-screen-large (= git-2026.142.39025-c3b9432-1)
```

安装：

```sh
opkg install /tmp/gl-screen-mudi7-i18n-zh-cn_2026.08.07.6_all.ipk
```

卸载：

```sh
opkg remove gl-screen-mudi7-i18n-zh-cn
```

## 源码结构

```text
sources/en          Mudi7 原版英文词典
sources/zh_cn       完整中文词典
config/             从 Mudi7 原版字体提取的尺寸参数
package/scripts/    安装、修改、备份和还原脚本
scripts/            字体准备、词典校验及 IPK 构建工具
overlay/            构建时生成的安装文件树
dist/               构建产物
```

字体使用 [IBM Plex Sans SC](https://github.com/IBM/plex/releases?q=sc)；详情见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本项目与 GL.iNet 官方无关联。
