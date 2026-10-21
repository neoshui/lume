# 开发环境 / Development setup

本文件说明如何在源码仓库中运行、检查和打包 Lume。当前主界面入口是 `main.py`，使用 PySide6 / Qt 6。

## 环境要求

### Linux

- Python 3.11 或更新版本，并带有 `venv` 与 `pip`。
- GNOME 桌面可启用完整快捷键和后台剪贴板集成；其他桌面环境仍可运行主界面，但集成功能可能不同。
- 建议使用 X11 或 Wayland 会话。入口会在 Wayland 会话中优先选择 Qt Wayland 插件；具体窗口定位能力取决于合成器。
- Linux 构建依赖 PyInstaller 所需的系统编译/运行库。已安装的桌面环境需具备 Qt 应用运行所需的图形库。

### Windows

- Python 3.11 或更新版本。
- 便携版构建需要 PySide6、PyInstaller、pypinyin 和 Pillow。
- 可选安装包还需要 Inno Setup 6，并能在 PowerShell 中调用 `ISCC.exe` 或 `iscc`。

## 创建环境并运行

Linux / macOS shell：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Windows PowerShell：

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

`requirements.txt` 包含应用运行依赖。构建脚本会安装固定版本的 PySide6、PyInstaller 和 pypinyin；Windows 构建脚本还会安装 Pillow。

## 测试与静态检查

```bash
# 编译 Python 源码
.venv/bin/python -m compileall -q lume main.py

# 运行单元测试
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

Windows PowerShell 中对应使用：

```powershell
 .venv\Scripts\python.exe -m compileall -q lume main.py
 $env:QT_QPA_PLATFORM = "offscreen"
 .venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试需要 Qt offscreen 平台插件。涉及 GNOME、全局快捷键、剪贴板 Shell 扩展、多显示器和窗口管理器行为的改动，也应在目标桌面会话中手工验证。

## 构建

### Linux

```bash
bash build_linux.sh
```

脚本在 `.venv` 中安装固定版本构建依赖，生成 PyInstaller **onedir** 目录：

```text
release/Lume-linux-x86_64/Lume
```

运行构建结果：

```bash
./release/Lume-linux-x86_64/Lume
```

若系统安装了 `appimagetool`，脚本还会尝试生成 AppImage。将 Linux 程序部署到当前用户：

```bash
bash scripts/install.sh
```

安装默认保留已有的自启动设置；可用 `--autostart` 启用，或用 `--no-autostart` 关闭。用户配置与历史保存在用户目录，不由构建脚本清除。

### Windows

在 PowerShell 中运行：

```powershell
./scripts/build_windows.ps1
```

输出便携版 `release/Lume-windows-x86_64-portable.exe`。安装 Inno Setup 6 后可生成安装包：

```powershell
./scripts/build_windows.ps1 -BuildInstaller
```

## 项目结构

- `main.py`：命令行选项、Qt 平台选择与应用入口。
- `lume/qt/main_window.py`：启动器主窗口及单实例服务。
- `lume/qt/widgets.py`：搜索与剪贴板自定义控件。
- `lume/qt/clipboard.py`：剪贴板历史存储和同步。
- `lume/qt/settings.py`：设置窗口。
- `lume/qt/smartisan.py`、`lume/resources/smartisan/`：Smartisan 风格样式和资源。
- `lume_shell_extension/`：GNOME Shell 剪贴板集成扩展。
- `tests/`：自动化测试。
- `scripts/`：安装、构建与辅助工具。

## 用户数据

运行源码或安装程序时均使用当前用户的数据目录：

- Linux 配置：`~/.config/lume/config.json`
- Linux 数据：`~/.local/share/lume/`

运行测试时建议使用临时 `HOME`，避免改动个人配置或剪贴板历史。请勿把真实用户剪贴板数据提交到仓库。

---

# Development setup

This guide covers running, checking, and packaging Lume from source. The current desktop UI starts at `main.py` and uses PySide6 / Qt 6.

## Requirements

### Linux

- Python 3.11 or newer, including `venv` and `pip`.
- A GNOME session enables the full shortcut and background clipboard integrations. The main window can run on other desktops, but integration behavior may differ.
- X11 or Wayland is recommended. On Wayland, the entry point prefers the Qt Wayland plugin when available; window placement capabilities depend on the compositor.
- Linux packaging requires the system libraries needed by PyInstaller and the Qt application runtime.

### Windows

- Python 3.11 or newer.
- PySide6, PyInstaller, pypinyin, and Pillow for the portable build.
- Inno Setup 6 is additionally required for the optional installer. `ISCC.exe` or `iscc` must be callable from PowerShell.

## Create an environment and run

Linux / macOS shell:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

`requirements.txt` lists runtime dependencies. Build scripts install pinned PySide6, PyInstaller, and pypinyin versions; the Windows build also installs Pillow.

## Tests and source checks

```bash
.venv/bin/python -m compileall -q lume main.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

For Windows PowerShell:

```powershell
.venv\Scripts\python.exe -m compileall -q lume main.py
$env:QT_QPA_PLATFORM = "offscreen"
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests require the Qt offscreen platform plugin. Changes involving GNOME, global shortcuts, the Shell clipboard extension, multiple monitors, or window-manager behavior should also be checked in the target desktop session.

## Build

### Linux

```bash
bash build_linux.sh
```

The script installs pinned build dependencies in `.venv` and creates this PyInstaller **onedir** bundle:

```text
release/Lume-linux-x86_64/Lume
```

Run it with:

```bash
./release/Lume-linux-x86_64/Lume
```

If `appimagetool` is installed, the script also attempts to create an AppImage. Install the Linux build for the current user with:

```bash
bash scripts/install.sh
```

The installer preserves the existing autostart choice by default. Use `--autostart` to enable autostart or `--no-autostart` to disable it. Build and install scripts do not clear user configuration or history.

### Windows

Run in PowerShell:

```powershell
./scripts/build_windows.ps1
```

This creates `release/Lume-windows-x86_64-portable.exe`. With Inno Setup 6 installed, create the installer using:

```powershell
./scripts/build_windows.ps1 -BuildInstaller
```

## Project layout

- `main.py`: command-line options, Qt platform selection, and application entry point.
- `lume/qt/main_window.py`: launcher window and single-instance service.
- `lume/qt/widgets.py`: custom search and clipboard widgets.
- `lume/qt/clipboard.py`: clipboard history storage and synchronization.
- `lume/qt/settings.py`: settings window.
- `lume/qt/smartisan.py`, `lume/resources/smartisan/`: Smartisan styling and assets.
- `lume_shell_extension/`: GNOME Shell clipboard integration.
- `tests/`: automated tests.
- `scripts/`: build, install, and helper scripts.

## User data

Source runs and installed builds use the current user's data directories:

- Linux configuration: `~/.config/lume/config.json`
- Linux data: `~/.local/share/lume/`

Use a temporary `HOME` for tests to avoid changing personal settings or clipboard history. Do not commit real clipboard contents.
