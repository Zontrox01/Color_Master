"""
ui/history_dialog.py
Diálogo de solo lectura que muestra el historial de colores
seleccionados y de mezclas calculadas (utils/history.py).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from utils.history import HistoryManager


def _swatch_label(hex_color: str, size: int = 20) -> QLabel:
    label = QLabel()
    label.setFixedSize(size, size)
    label.setStyleSheet(
        f"background-color: {hex_color}; border: 1px solid #999; border-radius: 3px;"
    )
    return label


class HistoryDialog(QDialog):
    def __init__(self, history: HistoryManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Historial")
        self.resize(480, 500)
        self._history = history

        tabs = QTabWidget()
        tabs.addTab(self._build_colors_tab(), "Colores")
        tabs.addTab(self._build_mixes_tab(), "Mezclas")

        layout = QVBoxLayout()
        layout.addWidget(tabs)

        close_row = QHBoxLayout()
        close_row.addStretch()
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        close_row.addWidget(btn_close)
        layout.addLayout(close_row)

        self.setLayout(layout)

    def _build_colors_tab(self) -> QWidget:
        list_widget = QListWidget()
        for hex_color, tipo, fecha in self._history.get_color_history(limit=100):
            item = QListWidgetItem(f"  {hex_color}   ({tipo})   —   {fecha}")
            item.setIcon(self._icon_for(hex_color))
            list_widget.addItem(item)

        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(list_widget)
        container.setLayout(layout)
        return container

    def _build_mixes_tab(self) -> QWidget:
        list_widget = QListWidget()
        for mix in self._history.get_mix_history(limit=100):
            componentes = ", ".join(
                f"{c['porcentaje']}% {c['nombre']}" for c in mix["componentes"]
            )
            texto = (
                f"{mix['fecha']}\n"
                f"Objetivo {mix['target_hex']} → resultado {mix['resulting_hex']} "
                f"(ΔE={mix['delta_e']:.2f})\n"
                f"{componentes}"
            )
            item = QListWidgetItem(texto)
            item.setIcon(self._icon_for(mix["resulting_hex"]))
            list_widget.addItem(item)

        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(list_widget)
        container.setLayout(layout)
        return container

    @staticmethod
    def _icon_for(hex_color: str):
        from PySide6.QtGui import QColor, QIcon, QPixmap

        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(hex_color))
        return QIcon(pixmap)
