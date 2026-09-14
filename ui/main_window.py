"""
ui/main_window.py
Ventana principal de ColorMaster.

Layout de 3 paneles:
- Izquierda: selector del color master y del master2 (para el gradiente
  de transición), más la info derivada (complementario, RGB/CMYK).
- Centro: las 5 filas de gradiente (brillo, saturación, tono, luminosidad,
  transición master->master2), en scroll vertical.
- Derecha: gestión de paleta del usuario y cálculo de mezclas
  (placeholder por ahora — se desarrolla en una fase posterior).
"""

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from core import color_math as cm
from ui.color_selector import ColorSelector
from ui.gradient_widget import GradientRow
from ui.palette_manager import PaletteManager
from ui.history_dialog import HistoryDialog
from utils.history import HistoryManager
from utils.exporters import export_report
from ui.theme import other_theme, apply_theme, DEFAULT_THEME

DEFAULT_STEPS = 10
MIN_STEPS = 3
MAX_STEPS = 27


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ColorMaster")
        self.resize(1280, 800)

        base_dir = Path(__file__).resolve().parent.parent  # raíz del proyecto
        ruta_icono = base_dir / "resources" / "color_master_icono.png"

        self.setWindowIcon(QIcon(str(ruta_icono)))

        self._steps = DEFAULT_STEPS
        self._history = HistoryManager()
        self._current_gradients = {}
        self._current_theme = DEFAULT_THEME

        self._build_left_panel()
        self._build_center_panel()
        self._build_right_panel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._left_panel)
        splitter.addWidget(self._center_scroll)
        splitter.addWidget(self._right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([300, 700, 300])

        self.setCentralWidget(splitter)

        # conectar señales y pintar el estado inicial
        self._master_selector.color_changed.connect(self._on_master_changed)
        self._master2_selector.color_changed.connect(self._on_master2_changed)
        self._steps_spinbox.valueChanged.connect(self._on_steps_changed)
        self._refresh_all()

    # -- panel izquierdo: selectores de color --------------------------------

    def _build_left_panel(self):
        self._btn_toggle_theme = QPushButton("🌙 Modo oscuro")
        self._btn_toggle_theme.clicked.connect(self._on_toggle_theme)

        self._master_selector = ColorSelector("Color master", "#3B82F6")
        self._master2_selector = ColorSelector("Color master 2 (para transición)", "#F59E0B")

        self._complementary_box = QGroupBox("Complementario")
        self._complementary_swatch = QLabel()
        self._complementary_swatch.setFixedSize(60, 60)
        self._complementary_label = QLabel()
        comp_layout = QHBoxLayout()
        comp_layout.addWidget(self._complementary_swatch)
        comp_layout.addWidget(self._complementary_label)
        comp_layout.addStretch()
        self._complementary_box.setLayout(comp_layout)

        history_box = QGroupBox("Historial")
        history_layout = QVBoxLayout()
        btn_view_history = QPushButton("Ver historial")
        btn_view_history.clicked.connect(self._open_history_dialog)
        btn_save_history = QPushButton("Guardar historial en archivo")
        btn_save_history.clicked.connect(self._on_save_history)
        btn_load_history = QPushButton("Cargar historial desde archivo")
        btn_load_history.clicked.connect(self._on_load_history)
        btn_clear_history = QPushButton("Borrar historial")
        btn_clear_history.clicked.connect(self._on_clear_history)
        for btn in (btn_view_history, btn_save_history, btn_load_history, btn_clear_history):
            history_layout.addWidget(btn)
        history_box.setLayout(history_layout)

        btn_export = QPushButton("Exportar a PDF")
        btn_export.clicked.connect(self._on_export_pdf)

        layout = QVBoxLayout()
        layout.addWidget(self._btn_toggle_theme)
        layout.addWidget(self._master_selector)
        layout.addWidget(self._master2_selector)
        layout.addWidget(self._complementary_box)
        layout.addWidget(history_box)
        layout.addWidget(btn_export)
        layout.addStretch()

        self._left_panel = QWidget()
        self._left_panel.setLayout(layout)

    # -- panel central: gradientes -------------------------------------------

    def _build_center_panel(self):
        self._row_brightness = GradientRow("Gradiente de brillo (HSV - V)")
        self._row_saturation = GradientRow("Gradiente de saturación (HSV - S)")
        self._row_hue = GradientRow("Gradiente de tono (rotación 360°)")
        self._row_lightness = GradientRow("Gradiente de luminosidad (HSL - L)")
        self._row_transition = GradientRow("Transición master → master2")

        controls_row = QHBoxLayout()
        controls_row.addWidget(QLabel("Colores por gradiente:"))
        self._steps_spinbox = QSpinBox()
        self._steps_spinbox.setRange(MIN_STEPS, MAX_STEPS)
        self._steps_spinbox.setValue(DEFAULT_STEPS)
        controls_row.addWidget(self._steps_spinbox)
        controls_row.addStretch()

        layout = QVBoxLayout()
        layout.addLayout(controls_row)
        for row in (
            self._row_brightness,
            self._row_saturation,
            self._row_hue,
            self._row_lightness,
            self._row_transition,
        ):
            layout.addWidget(row)
        layout.addStretch()

        content = QWidget()
        content.setLayout(layout)

        self._center_scroll = QScrollArea()
        self._center_scroll.setWidgetResizable(True)
        self._center_scroll.setWidget(content)

    # -- panel derecho: paleta / mezclas (placeholder) -----------------------

    def _build_right_panel(self):
        self._palette_manager = PaletteManager()
        self._right_panel = self._palette_manager

    # -- lógica: recalcular todo cuando cambia un color ----------------------

    def _on_toggle_theme(self):
        from PySide6.QtWidgets import QApplication
        self._current_theme = other_theme(self._current_theme)
        apply_theme(QApplication.instance(), self._current_theme)
        self._btn_toggle_theme.setText(
            "☀️ Modo claro" if self._current_theme == "dark" else "🌙 Modo oscuro"
        )

    def _on_master_changed(self, hex_color: str):
        self._history.log_color(hex_color, tipo="master")
        self._refresh_all()

    def _on_master2_changed(self, hex_color: str):
        self._history.log_color(hex_color, tipo="master2")
        self._refresh_all()

    def _open_history_dialog(self):
        dialog = HistoryDialog(self._history, parent=self)
        dialog.exec()

    def _on_save_history(self):
        from datetime import datetime as _dt
        default_name = f"colormaster_historial_{_dt.now().strftime('%Y%m%d_%H%M')}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar historial", default_name, "Archivos JSON (*.json)"
        )
        if not path:
            return
        try:
            self._history.export_to_file(path)
        except Exception as e:
            QMessageBox.warning(self, "No se pudo guardar", str(e))
            return
        QMessageBox.information(self, "Historial guardado", f"Guardado en:\n{path}")

    def _on_load_history(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Cargar historial", "", "Archivos JSON (*.json)"
        )
        if not path:
            return

        modo_box = QMessageBox(self)
        modo_box.setWindowTitle("Cargar historial")
        modo_box.setText(
            "¿Quieres añadir el historial del archivo al actual, o sustituir el actual por el del archivo?"
        )
        btn_add = modo_box.addButton("Añadir", QMessageBox.ButtonRole.AcceptRole)
        btn_replace = modo_box.addButton("Sustituir", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = modo_box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        modo_box.exec()
        elegido = modo_box.clickedButton()

        if elegido is btn_cancel or elegido is None:
            return

        if elegido is btn_replace:
            respuesta = QMessageBox.question(
                self,
                "Sustituir historial",
                "¿Quieres guardar el historial actual en un archivo antes de sustituirlo?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if respuesta == QMessageBox.StandardButton.Cancel:
                return
            if respuesta == QMessageBox.StandardButton.Yes:
                from datetime import datetime as _dt
                default_name = f"colormaster_historial_{_dt.now().strftime('%Y%m%d_%H%M')}.json"
                save_path, _ = QFileDialog.getSaveFileName(
                    self, "Guardar historial antes de sustituir", default_name, "Archivos JSON (*.json)"
                )
                if not save_path:
                    return  # canceló el guardado -> tampoco sustituimos
                try:
                    self._history.export_to_file(save_path)
                except Exception as e:
                    QMessageBox.warning(self, "No se pudo guardar", str(e))
                    return
            self._history.clear_all()

        try:
            self._history.import_from_file(path)
        except Exception as e:
            QMessageBox.warning(self, "No se pudo cargar", str(e))
            return

        accion = "sustituido" if elegido is btn_replace else "añadido al actual"
        QMessageBox.information(self, "Historial cargado", f"El historial del archivo se ha {accion}.")

    def _on_clear_history(self):
        respuesta = QMessageBox.question(
            self,
            "Borrar historial",
            "¿Quieres guardar el historial actual en un archivo antes de borrarlo?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if respuesta == QMessageBox.StandardButton.Cancel:
            return
        if respuesta == QMessageBox.StandardButton.Yes:
            from datetime import datetime as _dt
            default_name = f"colormaster_historial_{_dt.now().strftime('%Y%m%d_%H%M')}.json"
            path, _ = QFileDialog.getSaveFileName(
                self, "Guardar historial antes de borrar", default_name, "Archivos JSON (*.json)"
            )
            if not path:
                return  # el usuario canceló el guardado -> no borramos tampoco
            try:
                self._history.export_to_file(path)
            except Exception as e:
                QMessageBox.warning(self, "No se pudo guardar", str(e))
                return

        self._history.clear_all()
        QMessageBox.information(self, "Historial borrado", "El historial se ha borrado.")

    def _on_export_pdf(self):
        from datetime import datetime as _dt
        default_name = f"colormaster_informe_{_dt.now().strftime('%Y%m%d_%H%M')}.pdf"

        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar informe a PDF", default_name, "Archivos PDF (*.pdf)"
        )
        if not path:
            return

        try:
            export_report(
                path,
                master_hex=self._master_selector.hex_color(),
                master2_hex=self._master2_selector.hex_color(),
                gradients=self._current_gradients,
                palette_name=self._palette_manager.get_current_palette_name(),
                palette_pigments=self._palette_manager.get_palette_pigments(),
                mix_result=self._palette_manager.get_last_mix_result(),
                recent_colors=self._history.get_color_history(limit=20),
                recent_mixes=self._history.get_mix_history(limit=20),
            )
        except Exception as e:
            QMessageBox.warning(self, "No se pudo exportar", str(e))
            return

        QMessageBox.information(self, "Exportado", f"Informe guardado en:\n{path}")

    def _on_steps_changed(self, value: int):
        self._steps = value
        self._refresh_all()

    def _refresh_all(self):
        master = self._master_selector.hex_color()
        master2 = self._master2_selector.hex_color()
        n = self._steps

        self._row_brightness.set_values(cm.gradient_brightness(master, n), master)
        self._row_saturation.set_values(cm.gradient_saturation(master, n), master)
        self._row_hue.set_values(cm.gradient_hue(master, n), master)
        self._row_lightness.set_values(cm.gradient_lightness(master, n), master)
        self._row_transition.set_values(cm.gradient_transition(master, master2, n))

        self._current_gradients = {
            "Brillo": cm.gradient_brightness(master, n),
            "Saturación": cm.gradient_saturation(master, n),
            "Tono": cm.gradient_hue(master, n),
            "Luminosidad": cm.gradient_lightness(master, n),
            "Transición master → master2": cm.gradient_transition(master, master2, n),
        }

        comp = cm.complementary(master)
        self._complementary_swatch.setStyleSheet(
            f"background-color: {comp}; border: 1px solid #888; border-radius: 4px;"
        )
        self._complementary_label.setText(comp)

        self._palette_manager.set_target_hex(master)
