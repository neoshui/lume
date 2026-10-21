# Lume

**Lume（浮光）** 是一款轻量的桌面启动器和剪贴板管理器。按快捷键即可呼出搜索面板，快速打开应用、文件夹、网址和命令，也可检索或复用剪贴板历史。

Lume 当前使用 **PySide6 / Qt 6** 构建主界面，并针对 Linux GNOME 桌面提供快捷键和后台剪贴板集成。界面采用 Smartisan 风格，可在设置中切换样式。

## 功能

- 搜索并启动已安装应用，查找文件夹、网址和命令。
- 保存文本与图片剪贴板历史，支持固定常用条目。
- 使用快捷键显示或隐藏启动器。
- 支持浅色、深色和 Smartisan 界面样式选项。
- Linux 提供 PyInstaller 目录版构建；Windows 提供便携版和可选安装包。

## 下载与安装

请从 [GitHub Releases](https://github.com/neoshui/lume/releases) 获取适用于你系统的版本。

Linux 源码构建和本地安装方法见 [开发环境说明](DEVELOPMENT.md)。

## 快捷键与数据

默认快捷键为 `Alt+Space`，可在设置中修改。快捷键注册方式取决于桌面环境和系统设置。

- 配置：`~/.config/lume/config.json`
- 数据和剪贴板历史：`~/.local/share/lume/`

卸载或升级时请先备份以上目录，以保留个人设置和剪贴板数据。

## 参与开发

开发环境准备、运行、测试和打包步骤见 [DEVELOPMENT.md](DEVELOPMENT.md)。

## License

请查看仓库中的许可证文件及各资源目录内的授权说明。

---

# Lume

**Lume** is a lightweight desktop launcher and clipboard manager. Open its search panel with a keyboard shortcut to launch applications, find folders, search the web, run commands, and reuse clipboard history.

The main interface is built with **PySide6 / Qt 6**. Lume includes desktop integration for Linux GNOME and offers a Smartisan-inspired interface style that can be selected in Settings.

## Features

- Search and launch installed applications; find folders, URLs, and commands.
- Keep text and image clipboard history, with support for pinning entries.
- Show or hide the launcher with a keyboard shortcut.
- Choose light, dark, and Smartisan interface styling options.
- Build a PyInstaller onedir package for Linux; build a portable executable or optional installer for Windows.

## Download and install

Get a release for your operating system from [GitHub Releases](https://github.com/neoshui/lume/releases).

For Linux source builds and local installation, see [Development setup](DEVELOPMENT.md).

## Shortcut and data

The default shortcut is `Alt+Space`. You can change it in Settings. Shortcut registration depends on the desktop environment and system configuration.

- Configuration: `~/.config/lume/config.json`
- Application data and clipboard history: `~/.local/share/lume/`

Back up these locations before uninstalling or upgrading if you want to retain your preferences and clipboard data.

## Contributing

See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup, running, testing, and packaging instructions.

## License

See the license file in this repository and the attribution files included with bundled resources.
