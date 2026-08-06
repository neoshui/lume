# Lume 开发与交接说明

> 当前主线是 PySide6 浮动启动器。本文档以当前代码为准，供后续 agent 直接接手。

## 当前状态

- 主 UI：PySide6 / Qt 6，入口为 `main.py`。
- 旧 GTK 前端仍保留，但仅作为回退，入口为 `main_gtk.py`。
- 运行平台：GNOME Wayland。为保证窗口能按坐标移动到鼠标所在显示器，入口在 Wayland 且存在 `DISPLAY` 时强制使用 Qt `xcb` 后端。
- 单实例服务名固定为 `com.lume.launcher.qt`，定义在 `lume/qt/main_window.py`。
- 快捷键默认 `Alt+Space`，通过 GNOME `gsettings` 自定义快捷键调用 `~/.local/bin/lume-launcher`。
- 配置：`~/.config/lume/config.json`。
- 数据：`~/.local/share/lume/`。

## 运行和验证

```bash
cd /home/neoshui/下载/hermesProject/fuguang-gnome

# 前台启动
.venv/bin/python main.py

# 桌面启动脚本
/home/neoshui/.local/bin/lume-launcher

# 编译检查
QT_QPA_PLATFORM=offscreen .venv/bin/python -m compileall -q lume main.py run.py main_qt.py

# 单元测试（当前 17 项）
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q

# 日志
tail -f /tmp/lume_desktop.log
```

当前启动脚本内容应等价于：

```sh
#!/bin/sh
cd /home/neoshui/下载/hermesProject/fuguang-gnome || exit 1
exec .venv/bin/python main.py >> /tmp/lume_desktop.log 2>&1
```

## 多实例问题（重要）

开发过程中曾多次更换单实例服务名，系统里一度同时存在 20 多个旧 `main.py` 进程，导致用户看到旧 UI、旧语言和旧布局。现在服务名已经固定，不要再为了刷新代码修改 `APP_SERVER_NAME`。

修改代码后需要重启时，先精确清理本项目实例：

```bash
pkill -TERM -f '\.venv/bin/python main.py'
/home/neoshui/.local/bin/lume-launcher
```

检查实际进程：

```bash
ps -eo pid,args | grep -E '\.venv/bin/python main.py' | grep -v grep
```

不要使用带项目绝对路径的 `pkill` 模式，因为进程参数实际显示为相对路径 `.venv/bin/python main.py`，会匹配不到。

## 当前架构

```text
main.py / run.py / main_qt.py
  └── lume.qt_app.run()
      └── lume.qt.main_window.run()
          ├── QApplication
          ├── QLocalServer / QLocalSocket 单实例切换
          └── LumeWindow
              ├── 搜索输入框
              ├── QListWidget 搜索结果（list / grid）
              ├── QSplitter
              ├── 剪贴板历史区
              └── TabbedSettingsDialog
```

模块结构（`lume/qt/` 包）：

| 文件 | 行数 | 职责 |
|---|---|---|
| `lume/qt_app.py` | 7 | **轻量入口**——仅 re-export `run()` |
| `lume/qt/main_window.py` | ~700 | `LumeWindow` 主窗口 + `run()` 入口 |
| `lume/qt/settings.py` | ~560 | `SettingsDialog` + `TabbedSettingsDialog` 设置窗口 |
| `lume/qt/widgets.py` | ~185 | 自定义控件：`ResultRow`、`ClipboardChip` |
| `lume/qt/clipboard.py` | ~124 | `ClipboardStore` 剪贴板历史存储 |
| `lume/qt/utils.py` | ~121 | 辅助函数：颜色/图标/快捷键绑定 |
| `lume/search.py` | ~830 | 应用/文件夹/网址/命令搜索、评分、安全计算器 |
| `lume/config.py` | ~162 | 默认配置、读写、旧配置迁移 |
| `lume/themes.py` | ~116 | 中文配色主题预设 |
| `lume/tools/usage.py` | ~84 | 应用使用频率排序 |
| `main_gtk.py` / GTK 模块 | — | 回退前端，不是当前主线 |

`SettingsDialog` 是早期单页设置类，当前实际使用的是 `TabbedSettingsDialog`。修改设置页面时不要改错类。

## 已实现功能

### 搜索结果

- 应用、文件夹、固定网址、搜索引擎、快捷命令统一返回 `SearchResult`。
- `ResultRow` 自绘选中背景，避免 Qt 动态样式在 `QListWidget` item widget 中失效。
- 选中高亮使用当前强调色，并根据背景亮度选择黑/白文字。
- 鼠标悬停会同步当前选中项；方向键和鼠标共用一个选中状态。
- 列表模式：`↑ / ↓` 导航。
- 网格模式：`← / → / ↑ / ↓` 按二维网格导航。
- 名称与描述会根据可用宽度做右侧省略，避免横向溢出。
- 可配置是否显示结果详情、是否显示悬停提示。
- 悬停提示为紧凑半透明样式；Qt 原生 `QToolTip` 没有真正的背景模糊，仅用透明背景模拟磨砂。

### 网格布局

- `QListWidget.IconMode` + 自定义 `ResultRow`。
- 网格列宽根据 viewport 动态计算，窗口调整大小后 `_update_grid_geometry()` 重新布局。
- 结果卡片采用左对齐并扩展到单元格，减少最后一列与滚动条之间的空白。
- 修改网格时必须实测 `visualItemRect()` 和 item widget `geometry()`，不要只看 `gridSize()`。

### 应用语言

- 无 PyGObject 时直接解析 `/usr/share/applications`、`/usr/local/share/applications` 和用户 `.desktop` 文件。
- 本地化字段优先级：`LANGUAGE`、`LC_MESSAGES`、`LANG`、Python locale。
- 忽略 `C` / `POSIX`，支持 `Name[zh_CN]` → `Name[zh]` → `Name` 回退。
- 应用缓存绑定语言环境 `_locale_key()`；语言环境变化后会重新加载。

### 剪贴板

- 文本和图片历史持久化到 `~/.local/share/lume/clipboard_history.json`。
- 图片保存于 `~/.local/share/lume/clipboard_images/`。
- 文本 chip、图片缩略图、固定、删除、清空、右键保存图片。
- 图片悬停预览按原图比例显示，基础比例经过用户多次调整，当前用户已认可剪贴板区域。
- 2026-07-29：Windows 的 Qt 剪贴板快照问题已修复：`QMimeData(source)` 在 PySide6 中不是复制构造函数，必须通过 `_snapshot_mime_data()` 显式物化图片或文字。
- GNOME Wayland 的后台历史必须由 Shell 权限组件完成：普通 Qt/GDK 客户端无法订阅后台 selection 变更，`wl-paste --watch` 又需要 GNOME 不提供的 data-control 协议；高频单次 `wl-paste` 会创建临时 surface 并导致 Dock 闪烁。Lume 自带的 `lume-clipboard@lume.app` GNOME Shell 扩展通过 `Meta.Selection owner-changed` 捕获文本与 PNG，并写入 `~/.local/share/lume/shell_clipboard/history.json`；Qt 前端读取该文件。安装必须使用 `gnome-extensions install --force <zip>` 注册（仅复制到扩展目录在 GNOME 50 上不会立即被识别）；应用内“设置 → 快捷键 → 安装并启用”与 `scripts/install_lume_shell_extension.sh` 均采用该流程。
- 2026-07-29：连续复制只保留最后一项的问题已经验证修复。**根因不是 Qt 导入时覆盖条目，而是 Shell 扩展处于 `ERROR` 状态**：`make_directory_with_parents()` 在第二次启用时对已存在的 `shell_clipboard/images` 目录抛出 `FILE_EXISTS`，扩展随即退出。修复后先 `query_exists()`，仅首次创建目录；扩展状态必须为 `ACTIVE`。
- 正常工作链路：GNOME Shell 的 `Meta.Selection owner-changed` 每次变化即触发扩展 `_capture()` → 文本直接追加、PNG 写到 `shell_clipboard/images/` 并追加元数据 → `history.json` 保留最近 200 条 → `ClipboardStore._sync_shell_history()` 导入完整列表。不要将该流程退化为“启动 Lume 后读取当前 Qt clipboard”，那必然只能得到最后一次复制。
- `ClipboardStore` 在 Shell 历史有效时以它为权威来源并整体同步，避免 Qt 前景监听与 Shell 后台监听造成重复条目；Windows 和没有启用扩展的情况才回退 Qt 快照路径。
- 每次修改 `lume_shell_extension/extension.js` 后，GNOME Shell 可能继续缓存旧 ES 模块；特别是旧版本已处于 `ERROR` 时，停用/启用未必刷新源码。升级扩展后应注销并重新登录 GNOME，再确认 `gnome-extensions info lume-clipboard@lume.app` 返回 `State: ACTIVE`。应用内 `is_enabled()` 不得只检查“Enabled”，必须拒绝 `ERROR` 状态。
- 推荐诊断命令：

  ```bash
  gnome-extensions info lume-clipboard@lume.app
  cat ~/.local/share/lume/shell_clipboard/history.json
  journalctl --user -b --no-pager | rg 'lume-clipboard|extension.js'
  ```

  预期是扩展 `Version: 2`、`State: ACTIVE`，且 `history.json` 中同时出现 `text` 和 `image` 条目。
- 接手排查时，至少要手工验证以下顺序：
  1. 先复制图片，再复制文本，打开 Lume，历史中应同时保留图片和文本；
  2. 先复制文本，再复制图片，打开 Lume，历史中应同时保留文本和图片；
  3. 连续复制两张不同截图，不应只保留最后一张；
  4. 连续复制两段不同文本，不应只保留最后一段。
  5. 在 Lume 隐藏时连续复制至少 3 条文本；打开 Lume 后应全部存在。
  6. 检查扩展状态不是仅 `Enabled: Yes`，而是 `State: ACTIVE`；若为 `ERROR`，先看 journal，再不要继续排查 Qt 轮询。

### 设置页面

页面：

1. 外观
2. 快捷键
3. 搜索 & 网址
4. 关于

外观页包括：

- `auto / light / dark` 基础模式。
- 独立的中文配色主题。
- 强调色预设与 QColorDialog 自定义颜色。
- 窗口宽高、垂直偏移、字体、透明度、圆角滑块。
- list / grid、结果密度、结果详情、悬停提示开关。

设置页面使用固定蓝灰色 UI，不跟随用户强调色染色；用户明确要求强调色只影响启动器主界面。

快捷键页通过 GNOME `gsettings` 注册：

```text
org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:
/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/lume/
```

快捷键捕获使用 `_pending_shortcut`，只有点击“保存”后才写入配置。`register_gnome_shortcut()` 会同步确保 custom-keybindings 列表、名称、命令和 binding 均存在，不能退回只写 binding 的旧实现。

Windows 使用 `lume/win32_hotkey.py` 的 `RegisterHotKey` + `QAbstractNativeEventFilter`。打开设置窗口后必须立即注销旧 Win32 热键，关闭设置后按保存/取消后的配置重新注册；否则在设置中按旧快捷键会切换并隐藏主窗口。Windows 热键解析不允许对未知按键静默回退为 `Space`，当前支持字母、数字、F1-F24、方向键及常用导航键。原生 `WM_HOTKEY` 回调必须通过 `QTimer.singleShot(0, ...)` 排队回 Qt 主循环，不能在 native event filter 中直接操作窗口。`Alt+Space` 是 Windows 系统窗口菜单快捷键，设置对话框通过 `nativeEvent()` 截获 `WM_SYSKEYDOWN`/`SC_KEYMENU`；快捷键页还提供“恢复 Alt+Space”按钮作为可靠回退。

Windows 应用搜索由 `search.py::_load_windows_apps()` 提供：递归扫描用户和公共 Start Menu 的 `.lnk`，并读取 `App Paths` 注册表默认值获得真实 exe 路径。搜索框在 Windows 使用 70ms 防抖，刷新结果前调用 `QToolTip.hideText()`，避免销毁 item widget 时原生提示窗口闪烁。Windows 启动应用、目录和网址必须使用 `os.startfile()`，不要改回 `cmd /c start`，否则 windowed 包仍可能闪出命令窗口。

`scripts/build_windows.bat` 中每一行 PyInstaller 参数末尾都必须保留 `^`；尤其 `--hidden-import "lume.win32_hotkey" ^` 后面还有 `winreg` 和 `main.py` 参数。

搜索 & 网址页中，“搜索引擎配置”和“固定网址快捷方式”是两个独立功能，不要合并。

### 窗口定位

- 唤醒时记录 `QGuiApplication.screenAt(QCursor.pos())` 返回的目标屏幕。
- 延迟居中时继续使用同一个 `_wake_screen`，避免回到上次窗口所在屏幕。
- `launcher_vertical_offset` 为有符号值：正值向上，负值向下。
- Wayland 下 Qt `move()` 不可靠，因此入口会在可用时使用 `xcb/XWayland`。

## 配置字段

默认值见 `lume/config.py`。核心字段：

```json
{
  "shortcut": "ALT+space",
  "launcher_width": 680,
  "launcher_height": 720,
  "launcher_vertical_offset": 140,
  "layout": "list",
  "result_density": "comfortable",
  "show_result_descriptions": true,
  "show_result_tooltips": true,
  "clipboard_max_entries": 50,
  "theme": "auto",
  "color_theme": "晨雾",
  "font_size": 15,
  "appearance": {
    "panel_opacity": 0.97,
    "panel_bg_rgb": "247, 249, 252",
    "panel_bg_dark_rgb": "30, 32, 38",
    "accent_color": "rgb(111, 148, 201)",
    "border_radius": 18
  },
  "search_engine": {
    "name": "Google",
    "url": "https://www.google.com/search?q={query}"
  },
  "web_shortcuts": [],
  "folder_shortcuts": []
}
```

运行时还会写入 `paned_position`。

> ℹ️ v1.0.0 之前的 fuguang 旧配置 (`~/.config/fuguang/`) 和数据 (`~/.local/share/fuguang/`) 迁移代码已封装为 `config._migrate_legacy()`，在首次启动时自动执行一次。新用户不会触发。


## 主题和配色约束

- 基础亮/暗模式与配色主题是两个维度，不要合并。
- 用户强调色不能改变设置窗口的固定蓝灰配色。
- 搜索结果选中背景必须明显，不能只用非常浅的混色。
- 搜索名称使用较柔和的深蓝灰、字号 14px、字重 600；详情文字对比度较低。
- 调整配色后同时验证浅色、暗色、自定义浅色和自定义深色的文字可读性。

## 图标状态与下一步待办

当前程序活动图标已经恢复为原始浅色版本：

- `lume-128.png`
- `lume-256.png`
- `lume-512.png`

用户实际希望在深色霓虹版本基础上继续修改：

- 编辑目标：`lume-512-bold.png`（同系列还有 `lume-256-bold.png`、`lume-128-bold.png`）。
- 只修改中央放大镜。
- 镜圈更粗、更圆润。
- 手柄缩短约 30%，略加粗，端点圆润。
- 放大镜整体放大约 12%。
- 深色底板、叠层卡片、青色光效、左侧装饰、右下金色星光必须保持不变。

已多次调用网络图像编辑服务，但请求 `chatgpt.com/backend-api/codex/images/edits` 持续返回 network error。没有生成或覆盖结果。接手 agent 可继续重试；生成后先保存为版本化文件（例如 `lume-512-bold-v2.png`），让用户确认后再替换活动图标。

仓库里还有一次失败的本地实验源 `lume-icon-v2.svg`，它不是当前活动图标，也不符合用户目标，不要作为新设计基础。

程序窗口会从项目根目录加载 `lume-256.png` 作为 `QMainWindow` 图标。系统菜单图标位于：

```text
~/.local/share/icons/hicolor/128x128/apps/com.lume.launcher.png
~/.local/share/icons/hicolor/256x256/apps/com.lume.launcher.png
~/.local/share/icons/hicolor/512x512/apps/com.lume.launcher.png
```

用户确认新图标后，需要同步这些系统图标并刷新图标缓存。

## 剪贴板历史（Wayland 下已知问题）

### 症状

窗口隐式/最小化后，用户复制多条内容（如图片→文字），打开 Lume 时只显示最后一条，中间内容丢失。

### 根因

Wayland 的 `wl_data_offer` 协议使用**懒读取模型**——`dataChanged` 信号触发时，`QClipboard.mimeData()` 返回的 `QMimeData` 对象只记录了可用的 MIME 类型，实际数据要到 `pixmap()` / `text()` 调用时才从 compositor 拉取。连续复制时，后一次复制可能在前一次的数据读取完成前就覆盖了剪贴板，导致中间内容永远读不到。

对比各平台的差异：

| 平台 | 剪贴板协议 | `dataChanged` 可靠性 | 读取延迟 |
|------|-----------|---------------------|---------|
| X11 | `Selection` / `Clipboard` | 信号可靠，数据同步读取 | 无 |
| Wayland | `wl_data_offer` | 信号可靠，但数据是**懒加载** | 有（需要 round-trip）|
| Windows | `WM_CLIPBOARDUPDATE` / `OleGetClipboard` | 信号可靠，数据同步读取 | 无 |

这也是为什么 `showMinimized()` 后数据仍会丢失——surface 虽然保持存活，但聚焦状态变化可能导致 compositor 延迟或合并剪贴板事件。

### 尝试过但无效的方案

1. **后台定时轮询**（250ms/700ms）—— 轮询永远无法抢救中间状态，剪贴板同一时刻只能存一个内容
2. **`setWindowOpacity(0.0)` + `lower()` 保持 surface 存活** —— 解决了 `dataChanged` 不触发的问题，但未解决 Wayland 的懒读取延迟
3. **移除 dataChanged 防抖** —— 解决的是不同问题

### 当前实现要点

`QMimeData` 没有可用的 PySide6 深拷贝构造。`ClipboardStore._snapshot_mime_data()` 会在 `dataChanged` 或轮询触发时，显式调用 `imageData()` / `text()` 并写入新的 `QMimeData`，随后只从这个已物化的快照读取。不要改回 `QMimeData(self.app.clipboard().mimeData())`，否则 Windows 延迟渲染的截图会再次丢失。

### 验证方法

```bash
# 测试截图 + 文字连续复制
QT_QPA_PLATFORM=wayland python main.py

# 在另一个终端：
wl-paste --type image/png > /tmp/test.png   # 截图
echo "hello" | wl-copy                       # 再复制文字

# 打开 Lume，检查剪贴板历史是否同时包含图片和文字
```

由于 offscreen 测试环境无法复现 Wayland 的懒读取行为，验证**必须在真实 Wayland 会话中进行**。

### 安全计算器

`search.py` 的计算器使用 AST 白名单解释器，不允许改回直接 `eval()`。当前测试覆盖相关安全行为。

### 拼音与模糊搜索

使用 `pypinyin` 库实现中文拼音搜索（惰性导入，未安装时回退为旧桩行为）：

| 匹配方式 | 示例 | 分值 |
|---------|------|------|
| 精确匹配 | `"Firefox"` → `"Firefox"` | 1000 |
| 前缀匹配 | `"fire"` → `"Firefox"` | 900 |
| 词边界匹配 | `"fire"` → `"Firefox"` | 800 |
| **全拼音精确** | `"weixin"` → `"微信"` | 760 |
| **拼音首字母** | `"wx"` → `"微信"` | 750 |
| **全拼音前缀** | `"wei"` → `"微信"` | 720 |
| **全拼音子串** | `"xin"` → `"微信"` | 680 |
| **缩写匹配** | `"vsc"` → `"Visual Studio Code"` | 630 |
| 子串匹配 | `"fox"` → `"Firefox"` | 500 |
| **子序列匹配** | `"frefx"` → `"Firefox"` | 200 |
| 逐字符匹配 | — | 100 |
| **Levenshtein 容错** | `"firefx"` → `"Firefox"` | 80 |

`pypinyin` 列在 `pyproject.toml` 的依赖中，同时添加到 `build_linux.sh`、`Lume.spec`、`build_windows.bat`/`.ps1` 的 hidden-import 列表。

### 日志系统

`lume/log_utils.py` 提供统一的日志模块：

- 输出到 `~/.local/share/lume/lume.log`（INFO 及以上）
- 同时输出到 stderr（WARNING 及以上）
- 所有 logger 自动放在 `lume.*` 命名空间下，handler 统一由 `lume` 根 logger 管理
- 日志格式：`2026-07-28 22:15:30 [lume.config 42 WARNING] message`
- 使用方式：`from lume.log_utils import get_logger; log = get_logger(__name__)`

### 搜索结果分类

搜索结果现在按类型分组显示分类标题：

| 分类 | 对应 action_type | 图标 |
|------|-----------------|------|
| ⌘ 快捷命令 | `calculator`, `timestamp`, `note` | — |
| 📦 应用 | `app` | — |
| 📁 文件夹 | `folder` | — |
| 🌐 网页 | `web`, `search` | — |

分类标题仅在列表模式（list）下显示，网格模式（grid）下隐藏。


## 交接建议

新 agent 开始工作时按顺序执行：

1. 阅读本文件、`lume/qt/main_window.py`、`lume/qt/settings.py`、`lume/config.py`、`lume/search.py`。
2. 运行编译检查和单元测试。
3. 用 `ps` 确认只有一个 Lume 进程。
4. 修改后终止旧实例并启动一次最新版。
5. UI 修改必须让用户截图验收，不要仅根据 offscreen 测试判断视觉效果。
6. 不要再次更改单实例服务名。

## 当前已知待办

| 待办 | 状态 |
|---|---|
| 深色霓虹图标局部修改 | 阻塞于网络图像编辑服务 |
| Windows 全局快捷键实现 | 尚未实现；当前仅 GNOME gsettings |
| KDE/XFCE/Sway 快捷键 | 尚未实现 |
| 文件搜索增强 | 当前仅基础目录搜索 |
| 插件系统 | 尚未实现 |
| 翻译命令 | 尚未实现 |
| **重构：Qt 前端拆分为 `lume/qt/` 模块包** | ✅ 已完成 |
| **清理旧配置迁移** | ✅ 已完成 |
| **拼音搜索 + 模糊匹配** | ✅ 已完成 |
| **日志系统** | ✅ 已完成 |
| **搜索结果分类标题** | ✅ 已完成 |
| 剪贴板同步（Wayland 多内容丢失） | 🔴 **未修复，见下方说明** |
| GNOME Wayland 后台剪贴板历史（连续复制后只剩最后一条） | ✅ 通过 Lume 自带 GNOME Shell 扩展捕获；扩展必须安装并启用 |


---

## 打包与分发

### Linux 构建

```bash
# 一键构建（单文件可执行，~68MB）
bash build_linux.sh

# 产物
release/
├── Lume-linux-x86_64          # 单文件可执行（推荐）
└── Lume-x86_64.AppImage       # AppImage（需安装 appimagetool，可选）
```

**单文件可执行** `Lume-linux-x86_64` 是 PyInstaller 打包的自解压 ELF 文件，包含 PySide6 全部依赖。在终端直接运行即可：

```bash
./release/Lume-linux-x86_64
```

安装到当前用户目录（不需要 sudo）：

```bash
bash scripts/install.sh
```

安装时可选登录启动。登录启动只驻留后台，不会自动弹出搜索窗口：

```bash
bash scripts/install.sh --autostart
# 或明确关闭
bash scripts/install.sh --no-autostart
```

安装后也可以在 Lume 设置 → 快捷键 → 启动设置中切换“登录系统后自动启动 Lume”。
Linux 使用 `~/.config/autostart/com.lume.launcher.desktop`，Windows 安装器使用当前用户的
`HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`，均不需要管理员权限。

开机启动使用后台参数：

```bash
Lume --background
```

它会启动剪贴板服务和系统托盘，但不会显示主窗口；主窗口仍由全局快捷键呼出。

或移动到系统路径：

```bash
cp release/Lume-linux-x86_64 ~/.local/bin/lume-launcher
```

系统要求：
- Linux x86_64 (任何发行版)
- GLibc >= 2.28 (Ubuntu 20.04+, Debian 11+, CentOS 8+)
- X11 或 Wayland 会话（GNOME/KDE/XFCE/Sway）
- 不需要安装 Python 或 PySide6

### 跨平台构建说明

| 平台 | 构建方式 | 要求 |
|------|---------|------|
| **Linux** | 本机构建，`bash build_linux.sh` | Python 3.11+，PySide6 |
| **Windows (GitHub)** | GitHub Actions `workflow_dispatch` 或 `v*` 标签 | GitHub Windows Runner |
| **Windows (本机)** | `scripts\build_windows.bat` | Windows 10/11，Python 3.12 |

**Windows 本机构建步骤**（备用方式）：
1. 安装 Python 3.12+：从 [python.org](https://www.python.org/downloads/) 下载安装
2. **必须勾选 "Add Python to PATH"**
3. 将项目源码复制到 Windows 本地目录
4. 双击 `scripts\build_windows.bat`，或运行 `scripts\build_windows.ps1 -BuildInstaller`
5. 构建完成，输出文件位于 `release\`

> ⚠️ 本机构建需要网络下载固定版本的 PySide6、PyInstaller、pypinyin、Pillow 和 Inno Setup。
> ⚠️ Windows 安装包第一阶段未进行代码签名，首次运行可能显示“未知发布者”。

### GitHub Actions 构建与发布

项目使用 `.github/workflows/build.yml`：

- 推送普通分支：运行 Linux 测试、Python 编译检查和 Shell/扩展语法检查。
- 在 Actions 页面手动运行：构建并上传 Linux 和 Windows 产物，不创建 Release。
- 推送版本标签：构建全部平台并创建 GitHub Release。

正式版本的三个版本来源必须一致：`pyproject.toml`、`lume/version.py` 和 Git 标签的基础版本。

```bash
# 例如当前项目版本为 1.1.0
git tag v1.1.0
git push origin main --tags
```

预发布标签也支持，例如 `v1.1.0-test.1`，会创建 GitHub Pre-release。

GitHub Release 产物：

```text
Lume-windows-x86_64-portable.exe
Lume-windows-x86_64-Setup.exe
Lume-linux-x86_64
```

Windows 安装器默认安装到用户目录，不修改 PATH；安装向导可选当前用户登录启动，设置中也可以随时切换。卸载不会删除用户配置或剪贴板历史数据。

### 安装/卸载

```bash
# 安装（Linux）
bash scripts/install.sh

# 卸载（Linux）
bash scripts/uninstall.sh  # 如果存在
```

### 典型文件结构（发布版）

```
release/
├── Lume-linux-x86_64
├── Lume-windows-x86_64-portable.exe
└── Lume-windows-x86_64-Setup.exe
```

首次运行会自动在 `~/.config/lume/` 和 `~/.local/share/lume/` 创建配置和数据目录。

### 调试发布版

```bash
# 前台运行（查看日志）
./release/Lume-linux-x86_64

# 如果启动失败，检查缺少的库
ldd release/Lume-linux-x86_64
```



### Windows 全局快捷键 & 后台运行

Windows 版本使用 Win32 API (`RegisterHotKey`) 注册全局快捷键，不需要依赖 GNOME gsettings。

- **系统托盘**：启动后会出现在系统托盘中，右键可显示/隐藏或退出
- **全局快捷键**：默认 Alt+Space，在设置页面中可修改
- **后台驻留**：关闭窗口不会退出程序，会最小化到系统托盘
- **完全退出**：托盘图标右键 → 退出

> ⚠️ Windows 构建脚本已包含 `win32_hotkey` 模块，重新构建即可使用。


### Windows 构建与常见问题

**构建方法**：
```cmd
scripts\build_windows.bat
# 或 PowerShell：
scripts\build_windows.ps1 -BuildInstaller
```

**产物**：

- `release\Lume-windows-x86_64-portable.exe`
- `release\Lume-windows-x86_64-Setup.exe`

**Windows 全局快捷键（Win32 API + Qt native event filter）**：
- 使用 `RegisterHotKey` 注册系统级热键
- 使用 `QAbstractNativeEventFilter` 捕获 `WM_HOTKEY` 消息
- 支持所有 `Alt/Ctrl/Shift/Win + 按键` 组合
- 设置中点击按钮捕获快捷键时，会临时注销热键以免干扰
- 设置窗口关闭后，自动用新快捷键重新注册
- 退出应用时自动注销热键

**系统托盘**：
- 启动后出现在系统托盘
- 右键菜单：显示/隐藏、退出
- 关闭窗口不会退出，最小化到托盘

**Q: 修改快捷键后不生效，还是 Alt+Space？**
A: 保存设置后会自动重新注册。如果 Windows 版本仍不生效，尝试：
  1. 检查是否以管理员身份运行（某些快捷键组合需要管理员权限）
  2. 检查快捷键是否被其他程序占用

**Q: PowerShell 提示 "UnauthorizedAccess"？**
A: 右键 `.ps1` → "Run with PowerShell" 自动绕过限制。
   或直接用 CMD 双击 `.bat`。

**Q: 找不到 PySide6？**
A: 构建脚本会安装固定版本依赖。若网络受限，先确认 Python 能访问 PyPI。
