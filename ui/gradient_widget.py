"""
ui/gradient_widget.py
Widget que pinta una fila de N rectángulos (por defecto 10) con su
código hexadecimal debajo de cada uno. Se reutiliza para los 5 tipos
de gradiente (brillo, saturación, tono, luminosidad, transición).
"""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class _Swatch(QWidget):
    """Un rectángulo individual con su etiqueta hex debajo."""

    def __init__(self, hex_color: str, size=(60, 40), master: bool = False, parent=None):
        super().__init__(parent)
        w, h = size

        self._rect = QLabel()
        self._rect.setFixedSize(w, h)
        border = "3px solid #222" if master else "1px solid #999"
        self._rect.setStyleSheet(
            f"background-color: {hex_color}; border: {border}; border-radius: 3px;"
        )

        self._label = QLabel(hex_color)
        self._label.setAlignment(Qt.AlignCenter)
        font = self._label.font()
        font.setPointSize(8)
        if master:
            font.setBold(True)
        self._label.setFont(font)

        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        layout.addWidget(self._rect, alignment=Qt.AlignCenter)
        layout.addWidget(self._label)
        self.setLayout(layout)


class GradientRow(QGroupBox):
    """Fila con `title` a la izquierda y N swatches en horizontal."""

    def __init__(self, title: str, hex_values: List[str] | None = None,
                 master_hex: str | None = None, parent=None):
        super().__init__(title, parent)
        self._row_layout = QHBoxLayout()
        self._row_layout.setSpacing(4)
        self.setLayout(self._row_layout)
        if hex_values:
            self.set_values(hex_values, master_hex)

    def set_values(self, hex_values: List[str], master_hex: str | None = None):
        # limpiar swatches anteriores
        while self._row_layout.count():
            item = self._row_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for hex_color in hex_values:
            is_master = master_hex is not None and hex_color.upper() == master_hex.upper()
            self._row_layout.addWidget(_Swatch(hex_color, master=is_master))
        self._row_layout.addStretch()
