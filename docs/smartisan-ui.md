# Lume Smartisan UI 适配

2026-10-16

## 使用

设置 → 外观 → 界面风格，可在 **Smartisan** 和 **Lume 经典** 之间切换。未指定界面风格的配置默认使用 Smartisan。

明暗模式仍支持跟随系统、浅色和深色。原始 Smartisan 规范没有暗色，Lume 的深色是按相同层次关系推导的适配。

Smartisan 使用统一的灰阶、低饱和蓝强调色及轻微纵向渐变；经典模式保留原有配色、透明度和圆角自定义。切换风格不覆盖原来的 appearance 配置。应用网格、空搜索显示选项、剪贴板流式布局、私密模式、双击固定、图片预览和快捷键共用原有行为。

## 实现

- `lume/qt/smartisan.py`：Qt 设计 token、图标路径、共用/主窗口/设置页样式。
- `lume/resources/smartisan/`：随构建分发的搜索、设置、勾选和下拉图标，附署名及许可证。
- `ui_style`：`smartisan` 或 `classic`，与 `theme`（明暗）及 `color_theme`（经典配色）独立。
- 主窗口保留四列网格和动态流式换行；私密模式仍是定宽盾牌按钮，启用时统一使用蓝色。
- 图片预览继续使用窗口内浮层，避免原生 Wayland 的跨屏独立浮层问题。
- Linux 目录构建与共享 Windows spec 均包含图标及许可文件。

## 来源

- https://github.com/lemonteaau/smartisan-ui-skill （参考版本 94af366d564653d02b5df5f81ff0a8d3f3c4ade4，MIT）
- Smartisan OS UI Kit (Unofficial)，Paix Chan，CC BY 4.0。
- 具体署名、修改说明与许可证见 `lume/resources/smartisan/ATTRIBUTION.md`、`LICENSE.txt`。
