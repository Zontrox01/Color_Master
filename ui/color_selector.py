"""
ui/color_selector.py
Selector de color reutilizable: botón que abre QColorDialog + campos
editables de HEX, RGB y CMYK sincronizados entre sí.
Se usa tanto para el color "master" como para "master2".
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from core import color_math as cm


class _ClickableSwatch(QLabel):
    """Rectángulo de color que actúa como botón: un clic abre el selector."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Clic para elegir un color")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ColorSelector(QGroupBox):
    """Emite color_changed(str) cada vez que el color hex válido cambia."""

    color_changed = Signal(str)

    def __init__(self, title: str = "Color", initial_hex: str = "#3B82F6", parent=None):
        super().__init__(title, parent)
        self._hex = initial_hex.upper()
        self._updating = False  # evita bucles de señales al sincronizar campos

        self._swatch = _ClickableSwatch()
        self._swatch.setFixedSize(60, 60)
        self._swatch.setStyleSheet(self._swatch_style(self._hex))
        self._swatch.clicked.connect(self._open_dialog)

        self._hex_edit = QLineEdit(self._hex)
        self._hex_edit.setMaxLength(7)
        self._hex_edit.editingFinished.connect(self._on_hex_edited)

        FIELD_WIDTH = 38

        self._r_edit = QLineEdit()
        self._g_edit = QLineEdit()
        self._b_edit = QLineEdit()
        for edit in (self._r_edit, self._g_edit, self._b_edit):
            edit.setFixedWidth(FIELD_WIDTH)
            edit.editingFinished.connect(self._on_rgb_edited)

        self._c_edit = QLineEdit()
        self._m_edit = QLineEdit()
        self._y_edit = QLineEdit()
        self._k_edit = QLineEdit()
        for edit in (self._c_edit, self._m_edit, self._y_edit, self._k_edit):
            edit.setFixedWidth(FIELD_WIDTH)
            edit.editingFinished.connect(self._on_cmyk_edited)

        self._build_layout()
        self._refresh_fields()

    # -- construcción de la interfaz -----------------------------------

    def _build_layout(self):
        top = QHBoxLayout()
        top.addWidget(self._swatch)
        top.addStretch()

        hex_row = QFormLayout()
        hex_row.addRow("HEX:", self._hex_edit)

        rgb_row = QHBoxLayout()
        rgb_row.addWidget(QLabel("RGB:"))
        rgb_row.addWidget(self._r_edit)
        rgb_row.addWidget(self._g_edit)
        rgb_row.addWidget(self._b_edit)
        rgb_row.addStretch()

        cmyk_row = QHBoxLayout()
        cmyk_row.addWidget(QLabel("CMYK:"))
        cmyk_row.addWidget(self._c_edit)
        cmyk_row.addWidget(self._m_edit)
        cmyk_row.addWidget(self._y_edit)
        cmyk_row.addWidget(self._k_edit)
        cmyk_row.addStretch()

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addLayout(hex_row)
        layout.addLayout(rgb_row)
        layout.addLayout(cmyk_row)
        self.setLayout(layout)

    @staticmethod
    def _swatch_style(hex_color: str) -> str:
        return f"background-color: {hex_color}; border: 1px solid #888; border-radius: 4px;"

    # -- sincronización de campos ----------------------------------------

    def _refresh_fields(self):
        self._updating = True
        try:
            info = cm.ColorInfo.from_hex(self._hex)
            self._swatch.setStyleSheet(self._swatch_style(self._hex))
            self._hex_edit.setText(self._hex)

            r, g, b = info.rgb
            self._r_edit.setText(str(round(r)))
            self._g_edit.setText(str(round(g)))
            self._b_edit.setText(str(round(b)))

            c, m, y, k = info.cmyk
            self._c_edit.setText(str(round(c)))
            self._m_edit.setText(str(round(m)))
            self._y_edit.setText(str(round(y)))
            self._k_edit.setText(str(round(k)))
        finally:
            self._updating = False

    def _set_hex(self, hex_color: str):
        hex_color = hex_color.upper()
        if not hex_color.startswith("#"):
            hex_color = "#" + hex_color
        try:
            cm.hex_to_rgb(hex_color)  # valida formato
        except Exception:
            return  # hex inválido: no se propaga el cambio
        if hex_color == self._hex:
            return
        self._hex = hex_color
        self._refresh_fields()
        self.color_changed.emit(self._hex)

    # -- manejadores de eventos -------------------------------------------

    def _open_dialog(self):
        color = QColorDialog.getColor(QColor(self._hex), self, "Selecciona un color")
        if color.isValid():
            self._set_hex(color.name())

    def _on_hex_edited(self):
        if self._updating:
            return
        self._set_hex(self._hex_edit.text().strip())

    def _on_rgb_edited(self):
        if self._updating:
            return
        try:
            r = float(self._r_edit.text())
            g = float(self._g_edit.text())
            b = float(self._b_edit.text())
        except ValueError:
            self._refresh_fields()
            return
        self._set_hex(cm.rgb_to_hex((r, g, b)))

    def _on_cmyk_edited(self):
        if self._updating:
            return
        try:
            c = float(self._c_edit.text())
            m = float(self._m_edit.text())
            y = float(self._y_edit.text())
            k = float(self._k_edit.text())
        except ValueError:
            self._refresh_fields()
            return
        self._set_hex(cm.cmyk_to_hex((c, m, y, k)))

    # -- API pública --------------------------------------------------------

    def hex_color(self) -> str:
        return self._hex

    def set_hex_color(self, hex_color: str):
        self._set_hex(hex_color)
