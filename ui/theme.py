"""
ui/theme.py
Carga y aplica las hojas de estilo QSS de resources/light_theme.qss y
resources/dark_theme.qss.
"""

from __future__ import annotations

from pathlib import Path

RESOURCES_DIR = Path(__file__).resolve().parent.parent / "resources"

THEMES = {
    "light": RESOURCES_DIR / "light_theme.qss",
    "dark": RESOURCES_DIR / "dark_theme.qss",
}

DEFAULT_THEME = "light"


def load_qss(theme_name: str) -> str:
    path = THEMES.get(theme_name)
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def apply_theme(app, theme_name: str):
    app.setStyleSheet(load_qss(theme_name))


def other_theme(theme_name: str) -> str:
    return "dark" if theme_name == "light" else "light"
