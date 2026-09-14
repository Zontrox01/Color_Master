"""
ui/palette_manager.py
Panel derecho de la ventana principal.

Estrategia de carga (importante para que esto siga siendo rápido con
miles de pigmentos): al arrancar solo se lee database/pigment_index.xlsx,
un archivo diminuto con una fila por cada combinación marca+tipo
disponible. El Excel real de un fabricante (que puede tener cientos de
colores) solo se carga cuando el usuario elige explorarlo. Los pigmentos
que el usuario añade a su paleta se guardan con todos sus datos
directamente en SQLite (ver database/db_manager.py), así que mostrar la
paleta guardada o calcular una mezcla nunca necesita releer ningún Excel
de fabricante, sin importar cuántos haya en el índice.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core import mixer as mx
from database.db_manager import DBManager
from ui.add_pigment_dialog import AddPigmentDialog
from utils.history import HistoryManager

DATABASE_DIR = Path(__file__).resolve().parent.parent / "database"
PIGMENT_INDEX_PATH = DATABASE_DIR / "pigment_index.xlsx"


def _swatch_icon(hex_color: str, size: int = 16) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(hex_color))
    return QIcon(pixmap)


class PaletteManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._target_hex = "#3B82F6"

        self._db = DBManager()
        self._history = HistoryManager()
        self._current_palette_id, self._current_palette_name = (
            self._db.get_or_create_default_palette()
        )

        self._index: List[dict] = []
        self._index_error: Optional[str] = None
        self._catalog_pigments: List[mx.Pigment] = []  # el fabricante actualmente cargado
        self._last_mix_result: Optional[dict] = None

        self._load_index()
        self._build_ui()
        if not self._index_error:
            self._reload_palette_combo()
            self._refresh_my_palette_list()

    # -- carga del índice (rápida: un archivo diminuto) --------------------------

    def _load_index(self):
        try:
            df = pd.read_excel(PIGMENT_INDEX_PATH)
            self._index = df.to_dict("records")
        except Exception as e:
            self._index = []
            self._index_error = f"No se pudo cargar {PIGMENT_INDEX_PATH.name}:\n{e}"

    # -- construcción de la interfaz -------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("<b>Paleta y mezclas</b>"))

        if self._index_error:
            error_label = QLabel(self._index_error)
            error_label.setWordWrap(True)
            error_label.setStyleSheet("color: #B91C1C;")
            layout.addWidget(error_label)
            self.setLayout(layout)
            return

        # -- paleta activa --------------------------------------------------
        palette_row = QHBoxLayout()
        self._palette_combo = QComboBox()
        self._palette_combo.currentIndexChanged.connect(self._on_palette_selected)
        palette_row.addWidget(self._palette_combo, stretch=1)
        for text, handler in (
            ("Nueva", self._on_new_palette),
            ("Renombrar", self._on_rename_palette),
            ("Eliminar", self._on_delete_palette),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            palette_row.addWidget(btn)
        layout.addLayout(palette_row)

        # -- explorar catálogo de un fabricante -------------------------------
        catalog_box = QGroupBox("Explorar catálogo de un fabricante")
        catalog_layout = QVBoxLayout()

        tipo_row = QHBoxLayout()
        tipo_row.addWidget(QLabel("Tipo de tinta:"))
        self._tipo_filter_combo = QComboBox()
        self._tipo_filter_combo.addItem("Todos los tipos")
        for tipo in self._all_known_tipos():
            self._tipo_filter_combo.addItem(tipo)
        self._tipo_filter_combo.currentIndexChanged.connect(self._on_tipo_filter_changed)
        tipo_row.addWidget(self._tipo_filter_combo, stretch=1)
        catalog_layout.addLayout(tipo_row)

        catalog_row = QHBoxLayout()
        self._catalog_combo = QComboBox()
        catalog_row.addWidget(self._catalog_combo, stretch=1)
        btn_load = QPushButton("Cargar")
        btn_load.clicked.connect(self._on_load_catalog)
        catalog_row.addWidget(btn_load)
        catalog_layout.addLayout(catalog_row)

        self._populate_catalog_combo()

        btn_add_pigment = QPushButton("+ Añadir fabricante o tinta")
        btn_add_pigment.clicked.connect(self._on_add_pigment)
        catalog_layout.addWidget(btn_add_pigment)

        self._catalog_status_label = QLabel("Ningún catálogo cargado todavía.")
        self._catalog_status_label.setWordWrap(True)
        catalog_layout.addWidget(self._catalog_status_label)

        self._catalog_search_edit = QLineEdit()
        self._catalog_search_edit.setPlaceholderText("Buscar por nombre…")
        self._catalog_search_edit.textChanged.connect(self._on_catalog_search_changed)
        catalog_layout.addWidget(self._catalog_search_edit)

        self._catalog_list = QListWidget()
        self._catalog_list.itemChanged.connect(self._on_catalog_item_changed)
        catalog_layout.addWidget(self._catalog_list)

        catalog_box.setLayout(catalog_layout)
        layout.addWidget(catalog_box, stretch=1)

        # -- mi paleta (todas las marcas ya añadidas) -------------------------
        my_palette_box = QGroupBox("Mi paleta (todas las marcas añadidas)")
        my_palette_layout = QVBoxLayout()

        self._my_palette_list = QListWidget()
        my_palette_layout.addWidget(self._my_palette_list)

        remove_row = QHBoxLayout()
        btn_remove = QPushButton("Quitar seleccionado de la paleta")
        btn_remove.clicked.connect(self._on_remove_from_palette)
        remove_row.addWidget(btn_remove)
        my_palette_layout.addLayout(remove_row)

        self._selected_count_label = QLabel("0 pigmentos en la paleta")
        my_palette_layout.addWidget(self._selected_count_label)

        my_palette_box.setLayout(my_palette_layout)
        layout.addWidget(my_palette_box, stretch=1)

        # -- cálculo de mezcla ------------------------------------------------
        mix_box = QGroupBox("Mezcla para el color master")
        mix_layout = QVBoxLayout()

        target_row = QHBoxLayout()
        self._target_swatch = QLabel()
        self._target_swatch.setFixedSize(28, 28)
        self._target_hex_label = QLabel(self._target_hex)
        target_row.addWidget(QLabel("Objetivo:"))
        target_row.addWidget(self._target_swatch)
        target_row.addWidget(self._target_hex_label)
        target_row.addStretch()
        mix_layout.addLayout(target_row)

        params_row = QHBoxLayout()
        params_row.addWidget(QLabel("Máx. pigmentos:"))
        self._max_pigments_spin = QSpinBox()
        self._max_pigments_spin.setRange(1, 4)
        self._max_pigments_spin.setValue(4)
        params_row.addWidget(self._max_pigments_spin)
        params_row.addStretch()
        mix_layout.addLayout(params_row)

        self._calc_button = QPushButton("Calcular mezcla óptima")
        self._calc_button.clicked.connect(self._on_calculate)
        mix_layout.addWidget(self._calc_button)

        result_row = QHBoxLayout()
        self._result_swatch = QLabel()
        self._result_swatch.setFixedSize(28, 28)
        self._result_swatch.setStyleSheet("border: 1px solid #999; border-radius: 3px;")
        self._result_label = QLabel("—")
        self._result_label.setWordWrap(True)
        result_row.addWidget(QLabel("Resultado:"))
        result_row.addWidget(self._result_swatch)
        result_row.addWidget(self._result_label, stretch=1)
        mix_layout.addLayout(result_row)

        self._components_label = QLabel("")
        self._components_label.setWordWrap(True)
        mix_layout.addWidget(self._components_label)

        mix_box.setLayout(mix_layout)
        layout.addWidget(mix_box)

        self.setLayout(layout)
        self._update_target_swatch()

    # -- gestión de la paleta activa ---------------------------------------------

    def _reload_palette_combo(self):
        self._palette_combo.blockSignals(True)
        self._palette_combo.clear()
        for pid, nombre, _fecha in self._db.list_palettes():
            self._palette_combo.addItem(nombre, userData=pid)
        idx = self._palette_combo.findData(self._current_palette_id)
        self._palette_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._palette_combo.blockSignals(False)

    def _on_palette_selected(self, index: int):
        if index < 0:
            return
        self._current_palette_id = self._palette_combo.itemData(index)
        self._current_palette_name = self._palette_combo.currentText()
        self._refresh_my_palette_list()
        self._refresh_catalog_checkstates()

    def _on_new_palette(self):
        nombre, ok = QInputDialog.getText(self, "Nueva paleta", "Nombre de la nueva paleta:")
        if not ok or not nombre.strip():
            return
        try:
            new_id = self._db.create_palette(nombre.strip())
        except Exception as e:
            QMessageBox.warning(self, "No se pudo crear la paleta", str(e))
            return
        self._current_palette_id = new_id
        self._current_palette_name = nombre.strip()
        self._reload_palette_combo()
        self._refresh_my_palette_list()
        self._refresh_catalog_checkstates()

    def _on_rename_palette(self):
        nuevo, ok = QInputDialog.getText(
            self, "Renombrar paleta", "Nuevo nombre:", text=self._current_palette_name
        )
        if not ok or not nuevo.strip():
            return
        try:
            self._db.rename_palette(self._current_palette_id, nuevo.strip())
        except Exception as e:
            QMessageBox.warning(self, "No se pudo renombrar", str(e))
            return
        self._current_palette_name = nuevo.strip()
        self._reload_palette_combo()

    def _on_delete_palette(self):
        if self._palette_combo.count() <= 1:
            QMessageBox.information(
                self, "No se puede eliminar", "Debe existir al menos una paleta."
            )
            return
        confirm = QMessageBox.question(
            self,
            "Eliminar paleta",
            f"¿Eliminar la paleta '{self._current_palette_name}' y todos sus pigmentos guardados?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._db.delete_palette(self._current_palette_id)
        self._current_palette_id, self._current_palette_name = (
            self._db.get_or_create_default_palette()
        )
        self._reload_palette_combo()
        self._refresh_my_palette_list()
        self._refresh_catalog_checkstates()

    # -- filtro de tipo + combo de catálogo (índice oficial + personalizados) ----

    def _all_known_tipos(self) -> List[str]:
        tipos = {entry["tipo"] for entry in self._index}
        tipos |= {tipo for _marca, tipo, _n in self._db.list_custom_catalogs()}
        return sorted(tipos)

    def _build_catalog_entries(self) -> List[dict]:
        """Une el índice oficial con los catálogos personalizados del
        usuario. Si una marca+tipo existe en ambos, se fusiona en una sola
        entrada (al cargarla se combinan los pigmentos de los dos)."""
        entries = []
        seen = {}
        for idx_entry in self._index:
            key = (idx_entry["marca"], idx_entry["tipo"])
            entry = {**idx_entry, "custom_count": 0, "origen": "catalogo"}
            entries.append(entry)
            seen[key] = entry

        for marca, tipo, count in self._db.list_custom_catalogs():
            key = (marca, tipo)
            if key in seen:
                seen[key]["custom_count"] = count
            else:
                entries.append({
                    "marca": marca, "tipo": tipo, "archivo": None, "num_colores": 0,
                    "fiabilidad": None, "fuente": "Personalizado",
                    "custom_count": count, "origen": "personalizado",
                })
        return entries

    def _populate_catalog_combo(self):
        tipo_filtro = self._tipo_filter_combo.currentText() if hasattr(self, "_tipo_filter_combo") else "Todos los tipos"
        self._catalog_combo.clear()
        for entry in self._build_catalog_entries():
            if tipo_filtro != "Todos los tipos" and entry["tipo"] != tipo_filtro:
                continue
            if entry["origen"] == "catalogo":
                extra = f" + {entry['custom_count']} tuyos" if entry["custom_count"] else ""
                label = f"{entry['marca']} — {entry['tipo']} ({entry['num_colores']} colores{extra})"
            else:
                label = f"{entry['marca']} — {entry['tipo']} ({entry['custom_count']} tuyos, fabricante personalizado)"
            self._catalog_combo.addItem(label, userData=entry)

    def _on_tipo_filter_changed(self):
        self._populate_catalog_combo()

    def _on_add_pigment(self):
        marcas_existentes = sorted({e["marca"] for e in self._index} | {m for m, _t, _n in self._db.list_custom_catalogs()})
        dialog = AddPigmentDialog(self._all_known_tipos(), marcas_existentes, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.result_data:
            return

        data = dialog.result_data
        if self._db.pigment_id_exists(data["pigment_id"]):
            confirm = QMessageBox.question(
                self, "Ya existe",
                f"Ya tienes un pigmento personalizado con ese nombre para "
                f"'{data['marca']} — {data['tipo']}'. ¿Sobrescribirlo?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        self._db.add_custom_pigment(
            data["pigment_id"], data["marca"], data["tipo"], data["nombre"],
            data["hex"], data["opacidad"], data["fiabilidad"], data["fuente"],
        )

        # refrescar filtro de tipos, combo de catálogos, y si el catálogo
        # recién ampliado es el que está cargado ahora mismo, refrescarlo también
        current_tipo = self._tipo_filter_combo.currentText()
        self._tipo_filter_combo.blockSignals(True)
        self._tipo_filter_combo.clear()
        self._tipo_filter_combo.addItem("Todos los tipos")
        for tipo in self._all_known_tipos():
            self._tipo_filter_combo.addItem(tipo)
        idx = self._tipo_filter_combo.findText(current_tipo)
        self._tipo_filter_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._tipo_filter_combo.blockSignals(False)

        self._populate_catalog_combo()

        if self._catalog_pigments and any(
            p.marca == data["marca"] and p.tipo == data["tipo"] for p in self._catalog_pigments
        ):
            self._reload_current_catalog(data["marca"], data["tipo"])
        elif not self._catalog_pigments:
            pass

        QMessageBox.information(
            self, "Añadido",
            f"'{data['nombre']}' añadido a {data['marca']} — {data['tipo']}."
        )

    # -- explorar catálogo (carga perezosa) --------------------------------------

    def _on_load_catalog(self):
        idx = self._catalog_combo.currentIndex()
        if idx < 0:
            return
        entry = self._catalog_combo.itemData(idx)
        self._load_catalog_entry(entry)

    def _load_catalog_entry(self, entry: dict):
        pigments: List[mx.Pigment] = []

        if entry.get("archivo"):
            try:
                df = pd.read_excel(DATABASE_DIR / entry["archivo"])
                pigments.extend(mx.Pigment.from_row(r.to_dict()) for _, r in df.iterrows())
            except Exception as e:
                QMessageBox.warning(self, "No se pudo cargar el catálogo", str(e))
                return

        custom_rows = self._db.list_custom_pigments(marca=entry["marca"], tipo=entry["tipo"])
        pigments.extend(mx.Pigment.from_row(r) for r in custom_rows)

        self._catalog_pigments = pigments

        oficiales = entry.get("num_colores", 0)
        personalizados = len(custom_rows)
        detalle = f"{oficiales} oficiales" + (f" + {personalizados} tuyos" if personalizados else "")
        self._catalog_status_label.setText(
            f"Cargado: {entry['marca']} — {entry['tipo']} ({detalle}, {len(pigments)} en total)"
        )
        self._catalog_search_edit.blockSignals(True)
        self._catalog_search_edit.clear()
        self._catalog_search_edit.blockSignals(False)
        self._populate_catalog_list()

    def _reload_current_catalog(self, marca: str, tipo: str):
        """Si el catálogo actualmente mostrado es justo el que se acaba de
        ampliar con un pigmento nuevo, lo recarga para que aparezca ya."""
        for entry in self._build_catalog_entries():
            if entry["marca"] == marca and entry["tipo"] == tipo:
                self._load_catalog_entry(entry)
                return

    def _filtered_catalog_pigments(self) -> List[mx.Pigment]:
        texto = self._catalog_search_edit.text().strip().lower()
        if not texto:
            return self._catalog_pigments
        return [p for p in self._catalog_pigments if texto in p.nombre.lower()]

    def _populate_catalog_list(self):
        current_palette_ids = self._db.get_pigment_ids(self._current_palette_id)

        self._catalog_list.blockSignals(True)
        self._catalog_list.clear()
        for pigment in self._filtered_catalog_pigments():
            item = QListWidgetItem(f"{pigment.nombre}")
            item.setIcon(_swatch_icon(pigment.hex))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if pigment.id in current_palette_ids
                else Qt.CheckState.Unchecked
            )
            item.setData(Qt.ItemDataRole.UserRole, pigment)
            self._catalog_list.addItem(item)
        self._catalog_list.blockSignals(False)

    def _on_catalog_search_changed(self, _texto: str):
        self._populate_catalog_list()

    def _refresh_catalog_checkstates(self):
        """Al cambiar de paleta activa, refleja qué pigmentos del catálogo
        actualmente cargado (si hay uno) pertenecen a la nueva paleta."""
        if self._catalog_pigments:
            self._populate_catalog_list()

    def _on_catalog_item_changed(self, item: QListWidgetItem):
        pigment: mx.Pigment = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self._db.add_pigment(
                self._current_palette_id,
                pigment.id, pigment.marca, pigment.tipo, pigment.nombre,
                pigment.hex, pigment.opacidad,
            )
        else:
            self._db.remove_pigment(self._current_palette_id, pigment.id)
        self._refresh_my_palette_list()

    # -- mi paleta (lectura directa de SQLite, sin depender de ningún catálogo) --

    def _refresh_my_palette_list(self):
        pigments = self._db.get_pigments(self._current_palette_id)

        self._my_palette_list.clear()
        for p in pigments:
            item = QListWidgetItem(f"{p['nombre']} ({p['marca']}, {p['tipo']}) — {p['hex']}")
            item.setIcon(_swatch_icon(p["hex"]))
            item.setData(Qt.ItemDataRole.UserRole, p)
            self._my_palette_list.addItem(item)

        self._selected_count_label.setText(f"{len(pigments)} pigmento(s) en la paleta")

    def _on_remove_from_palette(self):
        item = self._my_palette_list.currentItem()
        if item is None:
            return
        pigment_data = item.data(Qt.ItemDataRole.UserRole)
        self._db.remove_pigment(self._current_palette_id, pigment_data["pigment_id"])
        self._refresh_my_palette_list()
        self._refresh_catalog_checkstates()

    def _current_palette_as_pigments(self) -> List[mx.Pigment]:
        return [mx.Pigment.from_row(p) for p in self._db.get_pigments(self._current_palette_id)]

    # -- color objetivo (viene del color master de la ventana principal) --------------

    def set_target_hex(self, hex_color: str):
        self._target_hex = hex_color.upper()
        if not self._index_error:
            self._update_target_swatch()

    def _update_target_swatch(self):
        self._target_hex_label.setText(self._target_hex)
        self._target_swatch.setStyleSheet(
            f"background-color: {self._target_hex}; border: 1px solid #888; border-radius: 3px;"
        )

    # -- cálculo de mezcla ----------------------------------------------------------

    def _on_calculate(self):
        selected = self._current_palette_as_pigments()
        if not selected:
            self._result_label.setText("Añade al menos un pigmento a tu paleta primero.")
            self._result_label.setStyleSheet("color: #B91C1C;")
            self._components_label.setText("")
            self._result_swatch.setStyleSheet(
                "background-color: #FFFFFF; border: 1px solid #999; border-radius: 3px;"
            )
            return

        max_pigments = self._max_pigments_spin.value()
        result = mx.suggest_mix(self._target_hex, selected, max_pigments=max_pigments)

        if result is None:
            self._result_label.setText("No se pudo calcular una mezcla.")
            self._result_label.setStyleSheet("color: #B91C1C;")
            self._components_label.setText("")
            return

        self._result_swatch.setStyleSheet(
            f"background-color: {result.resulting_hex}; border: 1px solid #999; border-radius: 3px;"
        )

        de = result.delta_e
        if de < 3:
            veredicto, color = "buena coincidencia", "#15803D"
        elif de < 6:
            veredicto, color = "coincidencia aceptable", "#B45309"
        else:
            veredicto, color = "coincidencia pobre", "#B91C1C"

        self._result_label.setText(f"{result.resulting_hex}  —  ΔE = {de:.2f} ({veredicto})")
        self._result_label.setStyleSheet(f"color: {color};")

        componentes = result.as_percentages()
        lines = [f"• {pct}% {p.nombre} ({p.marca})" for p, pct in componentes]
        self._components_label.setText("\n".join(lines))

        self._last_mix_result = {
            "target_hex": self._target_hex,
            "resulting_hex": result.resulting_hex,
            "delta_e": de,
            "componentes": [
                {"nombre": p.nombre, "marca": p.marca, "porcentaje": pct}
                for p, pct in componentes
            ],
        }

        self._history.log_mix(
            target_hex=self._target_hex,
            resulting_hex=result.resulting_hex,
            delta_e=de,
            componentes=self._last_mix_result["componentes"],
        )

    # -- API pública para exportación (main_window.py / exporters.py) ---------------

    def get_palette_pigments(self) -> List[dict]:
        return self._db.get_pigments(self._current_palette_id)

    def get_current_palette_name(self) -> str:
        return self._current_palette_name

    def get_last_mix_result(self) -> Optional[dict]:
        return self._last_mix_result
