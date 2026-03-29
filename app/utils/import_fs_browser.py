# Path: app/utils/import_fs_browser.py
"""Безопасный обзор папок на машине сервера для формы импорта (путь не доступен из JS в браузере)."""

from __future__ import annotations

import os
import string


def _allowed_roots():
    raw = (os.getenv("IMPORT_BROWSER_ROOTS") or "").strip()
    if not raw:
        return None
    return [os.path.normpath(x.strip()) for x in raw.split(",") if x.strip()]


def _path_allowed(resolved: str, roots) -> bool:
    if roots is None:
        return True
    resolved = os.path.abspath(resolved)
    for r in roots:
        try:
            base = os.path.abspath(r)
        except OSError:
            continue
        if resolved == base or resolved.startswith(base + os.sep):
            return True
    return False


def _is_windows_drive_root(path: str) -> bool:
    p = os.path.normpath(path)
    return len(p) == 3 and p[1] == ":" and p[2] == os.sep


def parent_directory(path: str) -> str | None:
    """Родительский каталог; пустая строка = «уровень дисков» (Windows). None = нет родителя."""
    if not path:
        return None
    path = os.path.normpath(path)
    if os.name != "nt" and path == os.path.sep:
        return None
    if os.name == "nt" and _is_windows_drive_root(path):
        return ""
    parent = os.path.dirname(path)
    if parent == path:
        return None
    return parent


def browse_directory(path_param: str) -> dict:
    """
    path_param '' — список дисков (Windows) или ['/'] (Unix).
    Иначе — содержимое каталога (только подпапки).
    """
    roots = _allowed_roots()
    path_param = (path_param or "").strip()

    if not path_param:
        if os.name == "nt":
            drives = []
            for letter in string.ascii_uppercase:
                root = f"{letter}:{os.sep}"
                if os.path.exists(root):
                    drives.append({"name": root, "path": root, "type": "drive"})
            return {
                "current": "",
                "current_label": "Диски",
                "parent": None,
                "can_go_up": False,
                "items": drives,
            }
        root = os.sep
        if not os.path.isdir(root):
            raise ValueError("Нет доступа к корню файловой системы")
        if not _path_allowed(root, roots):
            raise ValueError("Путь запрещён настройкой IMPORT_BROWSER_ROOTS")
        return {
            "current": root,
            "current_label": root,
            "parent": None,
            "can_go_up": False,
            "items": _list_subdirs(root, roots),
        }

    target = os.path.normpath(path_param)
    if not os.path.isdir(target):
        raise ValueError("Указанный путь не является папкой")

    if not _path_allowed(target, roots):
        raise ValueError("Путь запрещён настройкой IMPORT_BROWSER_ROOTS")

    parent = parent_directory(target)
    can_go_up = parent is not None
    label = target
    if os.name == "nt" and _is_windows_drive_root(target):
        label = target

    return {
        "current": target,
        "current_label": label,
        "parent": parent if can_go_up else None,
        "can_go_up": can_go_up,
        "items": _list_subdirs(target, roots),
    }


def _list_subdirs(target: str, roots) -> list:
    items = []
    try:
        names = os.listdir(target)
    except OSError as e:
        raise PermissionError(str(e)) from e

    for name in sorted(names, key=str.lower):
        if name in (".", ".."):
            continue
        full = os.path.join(target, name)
        try:
            if not os.path.isdir(full):
                continue
            if not _path_allowed(full, roots):
                continue
        except OSError:
            continue
        items.append({"name": name, "path": full, "type": "dir"})
    return items
