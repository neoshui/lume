"""Application, folder, and web search engine for Lume."""

import ast
import math
import operator
import os
import json
import shutil
import sys
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

try:
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio
except (ImportError, ValueError):
    Gio = None
import time
import locale
from urllib.parse import quote

from lume.tools.usage import get_sorted_by_frequency


CATEGORY_LABELS = {
    "calculator": "⌘ 快捷命令",
    "timestamp": "⌘ 快捷命令",
    "note": "⌘ 快捷命令",
    "clipboard": "⌘ 快捷命令",
    "app": "📦 应用",
    "folder": "📁 文件夹",
    "web": "🌐 网页",
    "search": "🌐 网页",
}
CATEGORY_ORDER = {
    "calculator": 0, "timestamp": 0, "note": 0, "clipboard": 0,
    "app": 1,
    "folder": 2,
    "web": 3,
    "search": 3,
}


def get_category(action_type: str) -> tuple[int, str]:
    """Return (sort_order, display_label) for a result's action_type."""
    label = CATEGORY_LABELS.get(action_type, "")
    order = CATEGORY_ORDER.get(action_type, 99)
    return (order, label)


class SearchResult(NamedTuple):
    """A single search result item."""
    name: str
    description: str
    icon: str  # icon name or file path
    action_type: str  # "app", "folder", "web", "clipboard", "tool"
    action_data: str  # app_id, path, url, etc.
    score: int = 0


# Cache for installed apps
_app_cache = []
_app_cache_loaded = False
_app_cache_locale = ""


def _locale_key() -> str:
    return "|".join(os.environ.get(name, "") for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"))


def _load_apps():
    """Load all installed desktop applications."""
    global _app_cache, _app_cache_loaded, _app_cache_locale
    current_locale = _locale_key()
    if _app_cache_loaded and _app_cache_locale == current_locale:
        return
    _app_cache = []
    _app_cache_locale = current_locale
    if sys.platform == "win32":
        _load_windows_apps()
        _app_cache_loaded = True
        return
    if Gio is None:
        _load_apps_from_desktop_files()
        _app_cache_loaded = True
        return
    for app in Gio.AppInfo.get_all():
        if not app.should_show():
            continue
        app_id = app.get_id() or ""
        name = app.get_display_name() or ""
        description = app.get_description() or ""
        icon_name = ""
        icon = app.get_icon()
        if icon:
            icon_name = icon.to_string() or ""
        _app_cache.append({
            "id": app_id,
            "name": name,
            "description": description,
            "icon": icon_name,
        })
    _app_cache.sort(key=lambda a: a["name"].lower())
    _app_cache_loaded = True


def _load_apps_from_desktop_files():
    """Fallback app discovery for environments without PyGObject."""
    import configparser

    roots = [
        Path.home() / ".local/share/applications",
        Path("/usr/local/share/applications"),
        Path("/usr/share/applications"),
    ]

    # Windows Start Menu shortcuts
    if sys.platform == "win32":
        _load_windows_apps()
        return

    # Linux: read .desktop files
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        for desktop_file in root.glob("*.desktop"):
            if desktop_file.name in seen:
                continue
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(desktop_file, encoding="utf-8")
                entry = parser["Desktop Entry"]
                if entry.get("Type", "Application") != "Application":
                    continue
                if entry.getboolean("NoDisplay", fallback=False) or entry.getboolean("Hidden", fallback=False):
                    continue
                def localized(key: str) -> str:
                    raw_locales = []
                    for env_name in ("LANGUAGE", "LC_MESSAGES", "LANG"):
                        raw_locales.extend(os.environ.get(env_name, "").split(":"))
                    detected = locale.getlocale(locale.LC_MESSAGES)[0]
                    if detected:
                        raw_locales.append(detected)
                    candidates = []
                    for raw in raw_locales:
                        lang = raw.split(".")[0].replace("-", "_")
                        if not lang or lang in ("C", "POSIX"):
                            continue
                        if lang not in candidates:
                            candidates.append(lang)
                        base = lang.split("_")[0]
                        if base not in candidates:
                            candidates.append(base)
                    values = {k.lower(): v for k, v in entry.items()}
                    for candidate in candidates:
                        value = values.get(f"{key}[{candidate}]".lower())
                        if value:
                            return value.strip()
                    return entry.get(key, "").strip()
                name = localized("Name")
                if not name:
                    continue
                seen.add(desktop_file.name)
                _app_cache.append({
                    "id": desktop_file.name,
                    "name": name,
                    "description": localized("Comment"),
                    "icon": entry.get("Icon", ""),
                })
            except (configparser.Error, OSError, UnicodeError):
                continue
    _app_cache.sort(key=lambda app: app["name"].lower())


def _load_windows_apps():
    """Discover installed apps from common Windows launcher sources."""
    from pathlib import Path as _Path
    import os as _os

    seen = set()
    shortcut_paths: list[str] = []

    def add_app(app_id: str, name: str, description: str = "", icon: str = ""):
        identity = app_id.casefold()
        if not name or identity in seen:
            return
        seen.add(identity)
        _app_cache.append({"id": app_id, "name": name, "description": description, "icon": icon})

    def scan_shortcut_dir(directory: _Path):
        if not directory.is_dir():
            return
        for shortcut in directory.rglob("*"):
            try:
                if shortcut.suffix.lower() != ".lnk":
                    continue
                shortcut_paths.append(str(shortcut))
            except Exception:
                continue

    appdata = _os.environ.get("APPDATA")
    if appdata:
        scan_shortcut_dir(_Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    programdata = _os.environ.get("PROGRAMDATA")
    if programdata:
        scan_shortcut_dir(_Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    userprofile = _os.environ.get("USERPROFILE")
    if userprofile:
        scan_shortcut_dir(_Path(userprofile) / "Desktop")
    public_dir = _os.environ.get("PUBLIC")
    if public_dir:
        scan_shortcut_dir(_Path(public_dir) / "Desktop")

    shortcut_targets = _resolve_windows_shortcuts(shortcut_paths)
    start_apps = _load_windows_start_apps()
    for shortcut_path in shortcut_paths:
        try:
            shortcut = _Path(shortcut_path)
            resolved = shortcut_targets.get(shortcut_path, {})
            name = str(
                _best_windows_app_name(
                    shortcut.stem,
                    resolved.get("display_name", ""),
                    resolved.get("target", ""),
                    start_apps,
                )
            ).strip()
            if not name or name.lower() in ("default", "desktop", "settings"):
                continue
            location = "Windows 开始菜单" if "start menu" in shortcut_path.lower() else "Windows 快捷方式"
            description = location
            if resolved.get("target"):
                description = resolved["target"]
            # For Start Menu/Desktop shortcuts, Windows launchers usually ask the
            # shell for the shortcut's own icon instead of substituting the target
            # path. Special system links (Control Panel, admin tools, shell items)
            # often render correctly only when the .lnk itself is used here.
            add_app(shortcut_path, name, description, shortcut_path)
        except Exception:
            continue

    # Also try reading from registry (App Paths + uninstall metadata).
    try:
        import winreg
        app_paths = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        uninstall_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]
        views = [0]
        if hasattr(winreg, "KEY_WOW64_64KEY"):
            views.extend([winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY])

        def open_key(root, path, access):
            try:
                return winreg.OpenKey(root, path, 0, winreg.KEY_READ | access)
            except OSError:
                return None

        for hkey in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for wow_access in views:
                key = open_key(hkey, app_paths, wow_access)
                if key is None:
                    continue
                with key:
                    index = 0
                    while True:
                        try:
                            app_name = winreg.EnumKey(key, index)
                            index += 1
                        except OSError:
                            break
                        if not app_name.lower().endswith(".exe"):
                            continue
                        subkey = open_key(key, app_name, wow_access)
                        if subkey is None:
                            continue
                        with subkey:
                            try:
                                executable, _ = winreg.QueryValueEx(subkey, "")
                            except OSError:
                                continue
                        executable = _os.path.expandvars(str(executable).strip().strip('"'))
                        if executable:
                            add_app(executable, _Path(app_name).stem, "Windows 应用", executable)

            for uninstall_path in uninstall_paths:
                for wow_access in views:
                    key = open_key(hkey, uninstall_path, wow_access)
                    if key is None:
                        continue
                    with key:
                        index = 0
                        while True:
                            try:
                                sub_name = winreg.EnumKey(key, index)
                                index += 1
                            except OSError:
                                break
                            subkey = open_key(key, sub_name, wow_access)
                            if subkey is None:
                                continue
                            with subkey:
                                try:
                                    display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                except OSError:
                                    continue
                                try:
                                    display_icon, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                                except OSError:
                                    display_icon = ""
                                try:
                                    install_location, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                                except OSError:
                                    install_location = ""
                            display_name = str(display_name).strip()
                            display_icon = _os.path.expandvars(str(display_icon).split(",")[0].strip().strip('"'))
                            install_location = _os.path.expandvars(str(install_location).strip().strip('"'))
                            if display_name:
                                add_app(
                                    display_icon or install_location or display_name,
                                    display_name,
                                    "Windows 已安装程序",
                                    display_icon or install_location,
                                )
    except Exception:
        pass
    _app_cache.sort(key=lambda app: app["name"].casefold())


def _normalize_windows_name(value: str) -> str:
    lowered = str(value or "").strip().casefold()
    return re.sub(r"[\s\-_().]+", "", lowered)


def _best_windows_app_name(stem: str, display_name: str, target: str, start_apps: dict[str, str]) -> str:
    candidates = [
        _normalize_windows_name(stem),
        _normalize_windows_name(display_name),
        _normalize_windows_name(Path(str(target)).stem if target else ""),
    ]
    for candidate in candidates:
        if candidate and candidate in start_apps:
            return start_apps[candidate]
    return display_name or stem


def _load_windows_start_apps() -> dict[str, str]:
    """Load localized Windows Start menu app names keyed by a normalized name."""
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        return {}
    script = r"""
$apps = Get-StartApps | Sort-Object Name -Unique | Select-Object Name, AppID
$apps | ConvertTo-Json -Compress -Depth 3
"""
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
            text=True,
            capture_output=True,
            check=True,
        )
        parsed = json.loads(result.stdout.strip() or "[]")
        if not parsed:
            return {}
        if isinstance(parsed, dict):
            parsed = [parsed]
        mapping = {}
        for item in parsed:
            if not isinstance(item, dict):
                continue
            name = str(item.get("Name", "")).strip()
            app_id = str(item.get("AppID", "")).strip()
            for key in {_normalize_windows_name(name), _normalize_windows_name(Path(app_id).stem)}:
                if key and name:
                    mapping.setdefault(key, name)
        return mapping
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        return {}


def _resolve_windows_shortcuts(shortcut_paths: list[str]) -> dict[str, dict[str, str]]:
    """Resolve .lnk display names/targets/icons via Windows Shell in one PowerShell call."""
    if not shortcut_paths:
        return {}
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        return {}
    script = r"""
$inputJson = [Console]::In.ReadToEnd()
$paths = ConvertFrom-Json $inputJson
$shell = New-Object -ComObject WScript.Shell
$shellApp = New-Object -ComObject Shell.Application
$resolved = @{}
foreach ($path in $paths) {
    try {
        $shortcut = $shell.CreateShortcut($path)
        $iconPath = ""
        $displayName = ""
        if ($shortcut.IconLocation) {
            $iconPath = ($shortcut.IconLocation -split ',')[0]
        }
        try {
            $folderPath = Split-Path -Parent $path
            $leafName = Split-Path -Leaf $path
            $folder = $shellApp.Namespace($folderPath)
            if ($folder) {
                $item = $folder.ParseName($leafName)
                if ($item) {
                    $displayName = $item.Name
                }
            }
        } catch {
        }
        $resolved[$path] = @{
            display_name = $displayName
            target = $shortcut.TargetPath
            icon = if ($iconPath) { $iconPath } else { $shortcut.TargetPath }
        }
    } catch {
    }
}
$resolved | ConvertTo-Json -Compress -Depth 4
"""
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
            input=json.dumps(shortcut_paths),
            text=True,
            capture_output=True,
            check=True,
        )
        parsed = json.loads(result.stdout.strip() or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        return {}


def _levenshtein(s1: str, s2: str) -> int:
    """Iterative Levenshtein distance for small-typo tolerance."""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def _is_subsequence(query: str, text: str) -> bool:
    """Check if all chars of query appear in text in order (case-insensitive).
    e.g. "frefx" is a subsequence of "Firefox".
    """
    text_lower = text.lower()
    query_lower = query.lower()
    i = 0
    for c in text_lower:
        if i < len(query_lower) and c == query_lower[i]:
            i += 1
    return i == len(query_lower)


def _get_acronym(text: str) -> str:
    """Extract first letter of each word.
    e.g. "Visual Studio Code" -> "vsco", "fIREFOX" -> "f"
    """
    words = re.split(r'[\s\-_.()]+', text)
    return ''.join(w[0].lower() for w in words if w and w[0].isalpha())


def _get_pinyin_full(text: str) -> str:
    """Return full pinyin without tone marks, or empty string if pypinyin unavailable.
    e.g. "微信" -> "weixin"
    """
    try:
        from pypinyin import lazy_pinyin
        return ''.join(lazy_pinyin(text)).lower()
    except ImportError:
        return ""


def _get_pinyin_initials(text: str) -> str:
    """Return pinyin initials (first letter of each character's pinyin).
    e.g. "微信" -> "wx",  "火狐浏览器" -> "hhlq"
    Falls back to a simple stub if pypinyin is not installed.
    """
    try:
        from pypinyin import lazy_pinyin
        initials = ''.join(p[0].lower() for p in lazy_pinyin(text) if p and p[0].isalpha())
        return initials
    except ImportError:
        pass

    # Fallback: try to find initials in parentheses first
    paren_match = re.search(r'\(([^)]+)\)', text)
    if paren_match:
        inner = paren_match.group(1)
        if inner.isascii():
            return inner.lower()

    # Basic stub fallback
    result = []
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            result.append(char.lower())
        elif char.isascii() and char.isalpha():
            result.append(char.lower())
    return ''.join(result)


def _score_match(query: str, text: str) -> int:
    """Score how well a query matches text. Supports:
    - Exact match           1000
    - Prefix match           900
    - Word boundary match    800
    - Full pinyin match      760-680
    - Pinyin initial match   750-650
    - Acronym/abbreviation   630-580
    - Substring match        500+
    - Subsequence match      200 (3+ chars)
    - Char-by-char match     100
    - Levenshtein fuzzy       80 (3+ chars, typo tolerance)
    """
    if not query or not text:
        return 0
    text_lower = text.lower()
    query_lower = query.lower()

    # Exact match (highest)
    if text_lower == query_lower:
        return 1000

    # Starts with query
    if text_lower.startswith(query_lower):
        return 900 - (len(text) - len(query)) * 5

    # Word boundary match (e.g., "fire" matches "Firefox")
    if text_lower.startswith(query_lower[0]) and query_lower in text_lower:
        words = re.split(r'[\s\-_]', text_lower)
        for i, word in enumerate(words):
            if word.startswith(query_lower):
                return 800 - i * 10

    # Full pinyin match (e.g., "weixin" matches "微信")
    full_pinyin = _get_pinyin_full(text)
    if full_pinyin:
        if query_lower == full_pinyin:
            return 760
        if full_pinyin.startswith(query_lower):
            return 720 - (len(full_pinyin) - len(query)) * 3
        if query_lower in full_pinyin:
            return 680 - (len(full_pinyin) - len(query)) * 2

    # Pinyin initial match (e.g., "wx" matches "微信")
    pinyin_initials = _get_pinyin_initials(text)
    if pinyin_initials:
        if query_lower == pinyin_initials:
            return 750
        if pinyin_initials.startswith(query_lower):
            return 700 - (len(pinyin_initials) - len(query)) * 5
        if query_lower in pinyin_initials:
            return 650 - (len(pinyin_initials) - len(query)) * 2

    # Acronym match (e.g., "ff" -> "Firefox", "vsc" -> "Visual Studio Code")
    acronym = _get_acronym(text)
    if acronym and len(acronym) >= 2:
        if query_lower == acronym:
            return 630
        if acronym.startswith(query_lower):
            return 600 - (len(acronym) - len(query)) * 3
        if query_lower in acronym:
            return 580

    # Contains query as substring
    if query_lower in text_lower:
        return 500 - (len(text) - len(query))

    # Subsequence match (e.g., "frefx" matches "Firefox")
    if len(query) >= 3 and _is_subsequence(query_lower, text_lower):
        return 200

    # Character-by-character match
    all_contained = all(c in text_lower or c == ' ' for c in query_lower)
    if all_contained:
        return 100

    # Fuzzy match via Levenshtein distance (typo tolerance)
    if len(query) >= 3 and len(text) >= 3:
        prefix = text_lower[:len(query) + 3]
        dist = _levenshtein(query_lower, prefix)
        max_dist = max(1, len(query) // 4)
        if dist <= max_dist:
            return 80 - dist * 10

    return 0


def search_apps(query: str, max_results: int = 12) -> list[SearchResult]:
    """Search installed applications by name/description."""
    _load_apps()
    if not query:
        # Return apps sorted by usage frequency
        sorted_apps = get_sorted_by_frequency(_app_cache)
        results = []
        for app in sorted_apps[:max_results]:
            results.append(SearchResult(
                name=app["name"],
                description=app["description"],
                icon=app["icon"],
                action_type="app",
                action_data=app["id"],
            ))
        return results

    scored = []
    for app in _app_cache:
        score = max(
            _score_match(query, app["name"]),
            _score_match(query, app["description"]),
        )
        if score > 0:
            scored.append((score, app))

    scored.sort(key=lambda x: -x[0])
    results = []
    for score, app in scored[:max_results]:
        results.append(SearchResult(
            name=app["name"],
            description=app["description"],
            icon=app["icon"],
            action_type="app",
            action_data=app["id"],
            score=score,
        ))
    return results


def search_folders(query: str, max_results: int = 6) -> list[SearchResult]:
    """Search home directory folders."""
    home = Path.home()
    results = []

    if not query:
        return results

    try:
        for entry in home.iterdir():
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            score = _score_match(query, entry.name)
            if score > 0:
                results.append(SearchResult(
                    name=entry.name,
                    description=str(entry),
                    icon="folder",
                    action_type="folder",
                    action_data=str(entry),
                    score=score,
                ))
    except PermissionError:
        pass

    results.sort(key=lambda x: -x.score)
    return results[:max_results]


def search_web_shortcuts(
    query: str, shortcuts: list[dict], max_results: int = 6
) -> list[SearchResult]:
    """Search configured web shortcuts."""
    results = []
    for sc in shortcuts:
        name = sc.get("name", "")
        url = sc.get("url", "")
        score = _score_match(query, name)
        if score > 0 or not query:
            results.append(SearchResult(
                name=f"🌐 {name}",
                description=url,
                icon="web-browser",
                action_type="web",
                action_data=url,
                score=score if query else 1,
            ))
    results.sort(key=lambda x: -x.score)
    return results[:max_results]


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_CALCULATOR_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "pow": pow,
}
_MAX_EXPRESSION_LENGTH = 200
_MAX_AST_NODES = 80
_MAX_ABSOLUTE_RESULT = 10 ** 100


def _evaluate_ast(node):
    """Evaluate only the small AST subset supported by the calculator."""
    if isinstance(node, ast.Expression):
        return _evaluate_ast(node.body)
    if isinstance(node, ast.Constant):
        if type(node.value) not in (int, float):
            raise ValueError("only numeric constants are supported")
        if not math.isfinite(node.value):
            raise ValueError("non-finite number")
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate_ast(node.left)
        right = _evaluate_ast(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("exponent is too large")
        return _BINARY_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_evaluate_ast(node.operand))
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_evaluate_ast(item) for item in node.elts]
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _CALCULATOR_FUNCTIONS:
            raise ValueError("unsupported function")
        if node.keywords:
            raise ValueError("keyword arguments are not supported")
        args = [_evaluate_ast(arg) for arg in node.args]
        return _CALCULATOR_FUNCTIONS[node.func.id](*args)
    raise ValueError(f"unsupported expression: {type(node).__name__}")


def _safe_eval(expr: str) -> str | None:
    """Evaluate a basic arithmetic expression without executing Python code."""
    if not expr or len(expr) > _MAX_EXPRESSION_LENGTH:
        return None
    try:
        tree = ast.parse(expr, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > _MAX_AST_NODES:
            return None
        result = _evaluate_ast(tree)
        if type(result) not in (int, float) or not math.isfinite(result):
            return None
        if abs(result) > _MAX_ABSOLUTE_RESULT:
            return None
        if isinstance(result, float) and result.is_integer():
            return str(int(result))
        if isinstance(result, float):
            return f"{result:.10g}"
        return str(result)
    except (ArithmeticError, MemoryError, RecursionError, SyntaxError, TypeError, ValueError):
        return None


def search_commands(query: str) -> list[SearchResult]:
    """Detect command patterns in query and return corresponding results."""
    if not query:
        return []

    results = []

    # === Calculator: =expression ===
    if query.startswith("=") and len(query) > 1:
        expr = query[1:].strip()
        if expr:
            result = _safe_eval(expr)
            if result is not None:
                results.append(SearchResult(
                    name=f"= {result}",
                    description=f"计算: {expr}",
                    icon="accessories-calculator",
                    action_type="calculator",
                    action_data=result,
                    score=1000,
                ))
            else:
                results.append(SearchResult(
                    name="表达式无效",
                    description="无法计算 — 仅支持基础数学运算",
                    icon="accessories-calculator",
                    action_type="clipboard",
                    action_data="",
                    score=0,
                ))

    # === Direct web search commands ===
    dir_commands = [
        ("g ", "Google", "https://www.google.com/search?q="),
        ("bd ", "百度", "https://www.baidu.com/s?wd="),
        ("gh ", "GitHub", "https://github.com/search?q="),
        ("yt ", "YouTube", "https://www.youtube.com/results?search_query="),
        ("bili ", "Bilibili", "https://search.bilibili.com/all?keyword="),
        ("zh ", "知乎", "https://www.zhihu.com/search?q="),
    ]
    for prefix, name, url in dir_commands:
        if query.lower().startswith(prefix):
            keyword = query[len(prefix):].strip()
            if keyword:
                search_url = url + quote(keyword)
                results.append(SearchResult(
                    name=f"🌐 在 {name} 搜索「{keyword}」",
                    description=search_url,
                    icon="web-browser",
                    action_type="search",
                    action_data=search_url,
                    score=950,
                ))

    # === Timestamp: ts ===
    if query.lower().strip() == "ts":
        now_ts = int(time.time())
        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        results.append(SearchResult(
            name=f"📋 复制时间戳: {now_ts}",
            description=f"当前时间: {now_str}",
            icon="edit-copy",
            action_type="timestamp",
            action_data=str(now_ts),
            score=1000,
        ))

    # === Quick note: note xxx ===
    if query.lower().startswith("note ") and len(query) > 5:
        content = query[5:].strip()
        results.append(SearchResult(
            name=f"📝 保存笔记",
            description=f"「{content[:50]}」",
            icon="text-x-generic",
            action_type="note",
            action_data=content,
            score=950,
        ))

    return results


def search(query: str, config: dict) -> list[SearchResult]:
    """Main search entry point - searches apps, commands, folders, web shortcuts, and web search."""
    results = []
    # Commands first (highest priority)
    results.extend(search_commands(query))
    results.extend(search_apps(query, config.get("max_results", 12)))
    results.extend(search_folders(query, 4))
    results.extend(search_web_shortcuts(
        query,
        config.get("web_shortcuts", []),
        4,
    ))
    # Add web search result for non-empty queries (always at bottom, score=0)
    if query:
        se = config.get("search_engine", {})
        engine_name = se.get("name", "Google")
        engine_url = se.get("url", "https://www.google.com/search?q={query}")
        search_url = engine_url.replace("{query}", quote(query.strip()))
        results.append(SearchResult(
            name=f"在 {engine_name} 搜索「{query}」",
            description=search_url,
            icon="web-browser",
            action_type="search",
            action_data=search_url,
            score=0,
        ))
    # Sort all results by score
    results.sort(key=lambda x: -x.score)
    return results[:config.get("max_results", 12)]


def launch_app(app_id: str):
    """Launch an application by its desktop file ID."""
    from lume.tools.usage import record_launch
    record_launch(app_id)
    if sys.platform == "win32":
        try:
            os.startfile(app_id)
            return True
        except OSError:
            return False
    import subprocess
    try:
        subprocess.Popen(
            ["gtk-launch", app_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except FileNotFoundError:
        pass
    # Fallback to GIO
    app = Gio.AppInfo.lookup(app_id) if Gio is not None else None
    if app:
        app.launch()
        return True
    return False


def open_folder(path: str):
    """Open a folder in the file manager."""
    expanded = os.path.expanduser(path)
    if sys.platform == "win32":
        try:
            os.startfile(expanded)
        except OSError:
            pass
        return
    import subprocess
    try:
        subprocess.Popen(
            ["xdg-open", expanded],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        if Gio is not None:
            Gio.AppInfo.launch_default_for_uri(Path(expanded).as_uri())


def open_url(url: str):
    """Open a URL in the default browser."""
    if sys.platform == "win32":
        try:
            os.startfile(url)
        except OSError:
            pass
        return
    import subprocess
    try:
        subprocess.Popen(
            ["xdg-open", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        if Gio is not None:
            Gio.AppInfo.launch_default_for_uri(url)
