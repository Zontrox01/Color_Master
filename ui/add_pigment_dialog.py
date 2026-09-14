"""
ui/add_pigment_dialog.py
Diálogo para que el usuario añada un pigmento propio: puede ser un
fabricante completamente nuevo, o una tinta más de un fabricante ya
existente en los catálogos oficiales (basta con escribir el mismo
nombre de marca).

El color se puede introducir de dos formas:
- Directa: eligiendo el hex con el mismo selector que el color master.
- Por L*a*b*: si el usuario tiene una ficha técnica del fabricante.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core import color_math as cm
from ui.color_selector import ColorSelector


class AddPigmentDialog(QDialog):
    """Al aceptar, el resultado está en self.result_data (dict) con:
    pigment_id, marca, tipo, nombre, hex, opacidad, fiabilidad, fuente."""

    def __init__(self, tipos_existentes: list[str], marcas_existentes: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Añadir fabricante o tinta")
        self.resize(420, 480)
        self.result_data: Optional[dict] = None

        layout = QVBoxLayout()

        # -- marca: existente (combo) o nueva (texto) --------------------------
        marca_box = QGroupBox("Marca")
        marca_layout = QVBoxLayout()

        marca_existente_row = QHBoxLayout()
        self._radio_marca_existente = QRadioButton("Fabricante existente:")
        self._radio_marca_existente.setChecked(True)
        self._marca_combo = QComboBox()
        self._marca_combo.addItems(sorted(marcas_existentes))
        marca_existente_row.addWidget(self._radio_marca_existente)
        marca_existente_row.addWidget(self._marca_combo, stretch=1)
        marca_layout.addLayout(marca_existente_row)

        marca_nueva_row = QHBoxLayout()
        self._radio_marca_nueva = QRadioButton("Fabricante nuevo:")
        self._marca_nueva_edit = QLineEdit()
        self._marca_nueva_edit.setEnabled(False)
        marca_nueva_row.addWidget(self._radio_marca_nueva)
        marca_nueva_row.addWidget(self._marca_nueva_edit, stretch=1)
        marca_layout.addLayout(marca_nueva_row)

        self._marca_group = QButtonGroup(self)
        self._marca_group.addButton(self._radio_marca_existente)
        self._marca_group.addButton(self._radio_marca_nueva)

        self._radio_marca_existente.toggled.connect(
            lambda checked: (self._marca_combo.setEnabled(checked), self._marca_nueva_edit.setEnabled(not checked))
        )
        if not marcas_existentes:
            self._radio_marca_nueva.setChecked(True)
            self._marca_combo.setEnabled(False)
            self._marca_nueva_edit.setEnabled(True)

        marca_box.setLayout(marca_layout)
        layout.addWidget(marca_box)

        # -- tipo: existente (combo) o nuevo (texto) -----------------------------
        tipo_box = QGroupBox("Tipo de tinta")
        tipo_layout = QVBoxLayout()

        tipo_existente_row = QHBoxLayout()
        self._radio_tipo_existente = QRadioButton("Tipo existente:")
        self._radio_tipo_existente.setChecked(True)
        self._tipo_combo = QComboBox()
        self._tipo_combo.addItems(sorted(set(tipos_existentes) | {"Acrilico", "Acuarela", "Oleo"}))
        tipo_existente_row.addWidget(self._radio_tipo_existente)
        tipo_existente_row.addWidget(self._tipo_combo, stretch=1)
        tipo_layout.addLayout(tipo_existente_row)

        tipo_nuevo_row = QHBoxLayout()
        self._radio_tipo_nuevo = QRadioButton("Tipo nuevo:")
        self._tipo_nuevo_edit = QLineEdit()
        self._tipo_nuevo_edit.setEnabled(False)
        tipo_nuevo_row.addWidget(self._radio_tipo_nuevo)
        tipo_nuevo_row.addWidget(self._tipo_nuevo_edit, stretch=1)
        tipo_layout.addLayout(tipo_nuevo_row)

        self._tipo_group = QButtonGroup(self)
        self._tipo_group.addButton(self._radio_tipo_existente)
        self._tipo_group.addButton(self._radio_tipo_nuevo)

        self._radio_tipo_existente.toggled.connect(
            lambda checked: (self._tipo_combo.setEnabled(checked), self._tipo_nuevo_edit.setEnabled(not checked))
        )

        tipo_box.setLayout(tipo_layout)
        layout.addWidget(tipo_box)

        # -- nombre del color -----------------------------------------------------
        nombre_form = QFormLayout()
        self._nombre_edit = QLineEdit()
        nombre_form.addRow("Nombre del color:", self._nombre_edit)
        layout.addLayout(nombre_form)

        # -- modo de entrada de color -----------------------------------------
        modo_row = QHBoxLayout()
        self._radio_hex = QRadioButton("Elegir color directamente")
        self._radio_lab = QRadioButton("Introducir valores L*a*b*")
        self._radio_hex.setChecked(True)
        self._modo_group = QButtonGroup(self)
        self._modo_group.addButton(self._radio_hex)
        self._modo_group.addButton(self._radio_lab)
        self._radio_hex.toggled.connect(self._on_modo_changed)
        self._radio_lab.toggled.connect(self._on_modo_changed)
        modo_row.addWidget(self._radio_hex)
        modo_row.addWidget(self._radio_lab)
        layout.addLayout(modo_row)

        self._stack = QStackedWidget()

        self._color_selector = ColorSelector("Color", "#808080")
        self._stack.addWidget(self._color_selector)

        lab_widget = QWidget()
        lab_form = QFormLayout()
        self._l_spin = QDoubleSpinBox()
        self._l_spin.setRange(0, 100)
        self._l_spin.setValue(50)
        self._a_spin = QDoubleSpinBox()
        self._a_spin.setRange(-128, 128)
        self._b_spin = QDoubleSpinBox()
        self._b_spin.setRange(-128, 128)
        lab_form.addRow("L*:", self._l_spin)
        lab_form.addRow("a*:", self._a_spin)
        lab_form.addRow("b*:", self._b_spin)
        self._lab_preview = QLabel()
        self._lab_preview.setFixedSize(50, 30)
        self._lab_preview.setStyleSheet("background-color: #808080; border: 1px solid #999;")
        lab_form.addRow("Previsualización:", self._lab_preview)
        for spin in (self._l_spin, self._a_spin, self._b_spin):
            spin.valueChanged.connect(self._update_lab_preview)
        lab_widget.setLayout(lab_form)
        self._stack.addWidget(lab_widget)

        layout.addWidget(self._stack)

        # -- opacidad, fiabilidad, fuente --------------------------------------
        extra_form = QFormLayout()
        self._opacidad_spin = QDoubleSpinBox()
        self._opacidad_spin.setRange(0.0, 1.0)
        self._opacidad_spin.setSingleStep(0.05)
        self._opacidad_spin.setValue(1.0)
        extra_form.addRow("Opacidad (0=transparente, 1=opaco):", self._opacidad_spin)

        self._fiabilidad_spin = QSpinBox()
        self._fiabilidad_spin.setRange(1, 5)
        self._fiabilidad_spin.setValue(2)
        extra_form.addRow("Fiabilidad del dato (1-5):", self._fiabilidad_spin)

        self._fuente_edit = QLineEdit("Introducido manualmente por el usuario")
        extra_form.addRow("Fuente:", self._fuente_edit)

        layout.addLayout(extra_form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def _on_modo_changed(self, checked: bool):
        self._stack.setCurrentIndex(0 if self._radio_hex.isChecked() else 1)

    def _update_lab_preview(self):
        hex_color = cm.lab_to_hex(self._l_spin.value(), self._a_spin.value(), self._b_spin.value())
        self._lab_preview.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #999;")

    def _on_accept(self):
        if self._radio_marca_existente.isChecked():
            if self._marca_combo.count() == 0:
                QMessageBox.warning(
                    self, "No hay fabricantes",
                    "Todavía no hay ningún fabricante en la base de datos. "
                    "Elige 'Fabricante nuevo' y escribe su nombre.",
                )
                return
            marca = self._marca_combo.currentText().strip()
        else:
            marca = self._marca_nueva_edit.text().strip()

        if self._radio_tipo_existente.isChecked():
            tipo = self._tipo_combo.currentText().strip()
        else:
            tipo = self._tipo_nuevo_edit.text().strip()

        nombre = self._nombre_edit.text().strip()

        if not marca or not tipo or not nombre:
            QMessageBox.warning(self, "Faltan datos", "Marca, tipo y nombre son obligatorios.")
            return

        if self._radio_hex.isChecked():
            hex_color = self._color_selector.hex_color()
        else:
            hex_color = cm.lab_to_hex(self._l_spin.value(), self._a_spin.value(), self._b_spin.value())

        pigment_id = cm.make_pigment_id(marca, tipo, nombre, prefix="custom__")

        self.result_data = {
            "pigment_id": pigment_id,
            "marca": marca,
            "tipo": tipo,
            "nombre": nombre,
            "hex": hex_color,
            "opacidad": self._opacidad_spin.value(),
            "fiabilidad": self._fiabilidad_spin.value(),
            "fuente": self._fuente_edit.text().strip() or "Introducido manualmente por el usuario",
        }
        self.accept()
