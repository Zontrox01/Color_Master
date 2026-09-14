"""
utils/history.py
Historial de colores seleccionados y de mezclas calculadas.

Usa el mismo archivo SQLite que database/db_manager.py (las paletas del
usuario), añadiendo dos tablas nuevas. Es una capa de datos pura, sin
dependencia de PySide6, para poder probarla sin levantar la interfaz.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from database.db_manager import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS color_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hex TEXT NOT NULL,
    tipo TEXT NOT NULL,           -- 'master', 'master2', etc.
    fecha TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mix_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_hex TEXT NOT NULL,
    resulting_hex TEXT NOT NULL,
    delta_e REAL NOT NULL,
    componentes_json TEXT NOT NULL,  -- [{"nombre":..,"marca":..,"porcentaje":..}, ...]
    fecha TEXT NOT NULL
);
"""


class HistoryManager:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # -- historial de colores ------------------------------------------------

    def log_color(
        self,
        hex_color: str,
        tipo: str = "master",
        avoid_consecutive_duplicates: bool = True,
        fecha: Optional[str] = None,
    ):
        """Registra un color. Si `avoid_consecutive_duplicates`, no duplica
        una entrada si es idéntica (mismo hex y tipo) a la última registrada.
        `fecha` permite preservar la fecha original al importar un historial
        guardado; si no se indica, se usa el momento actual."""
        hex_color = hex_color.upper()
        if avoid_consecutive_duplicates:
            last = self.get_color_history(limit=1, tipo=tipo)
            if last and last[0][0] == hex_color:
                return
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO color_history (hex, tipo, fecha) VALUES (?, ?, ?)",
                (hex_color, tipo, fecha or datetime.now().isoformat(timespec="seconds")),
            )

    def get_color_history(
        self, limit: Optional[int] = 50, tipo: Optional[str] = None
    ) -> List[Tuple[str, str, str]]:
        """Devuelve [(hex, tipo, fecha), ...] más recientes primero.
        `limit=None` devuelve todo el historial, sin límite."""
        query = "SELECT hex, tipo, fecha FROM color_history"
        params: list = []
        if tipo is not None:
            query += " WHERE tipo = ?"
            params.append(tipo)
        query += " ORDER BY id DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            cur = conn.execute(query, params)
            return cur.fetchall()

    def clear_color_history(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM color_history")

    # -- historial de mezclas -------------------------------------------------

    def log_mix(
        self,
        target_hex: str,
        resulting_hex: str,
        delta_e: float,
        componentes: List[dict],
        fecha: Optional[str] = None,
    ):
        """`componentes` es una lista de dicts: {"nombre", "marca", "porcentaje"}.
        `fecha` permite preservar la fecha original al importar."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO mix_history
                   (target_hex, resulting_hex, delta_e, componentes_json, fecha)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    target_hex.upper(),
                    resulting_hex.upper(),
                    float(delta_e),
                    json.dumps(componentes, ensure_ascii=False),
                    fecha or datetime.now().isoformat(timespec="seconds"),
                ),
            )

    def get_mix_history(self, limit: Optional[int] = 50) -> List[dict]:
        """Devuelve una lista de dicts con las mezclas más recientes primero.
        `limit=None` devuelve todo el historial, sin límite."""
        query = "SELECT target_hex, resulting_hex, delta_e, componentes_json, fecha FROM mix_history ORDER BY id DESC"
        params: list = []
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            cur = conn.execute(query, params)
            rows = cur.fetchall()

        result = []
        for target_hex, resulting_hex, delta_e, componentes_json, fecha in rows:
            result.append(
                {
                    "target_hex": target_hex,
                    "resulting_hex": resulting_hex,
                    "delta_e": delta_e,
                    "componentes": json.loads(componentes_json),
                    "fecha": fecha,
                }
            )
        return result

    def clear_mix_history(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM mix_history")

    def clear_all(self):
        self.clear_color_history()
        self.clear_mix_history()

    # -- exportar / importar a un archivo --------------------------------------

    def export_to_file(self, path: str):
        """Guarda TODO el historial (sin límite) en un .json, tal cual, para
        poder recuperarlo más tarde con import_from_file()."""
        data = {
            "colores": [
                {"hex": h, "tipo": t, "fecha": f}
                for h, t, f in self.get_color_history(limit=None)
            ],
            "mezclas": self.get_mix_history(limit=None),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def import_from_file(self, path: str):
        """Añade al historial actual el contenido de un .json guardado con
        export_to_file(). No borra lo que ya hubiera; se suma."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for c in data.get("colores", []):
            self.log_color(
                c["hex"], tipo=c.get("tipo", "master"),
                avoid_consecutive_duplicates=False, fecha=c.get("fecha"),
            )
        for m in data.get("mezclas", []):
            self.log_mix(
                m["target_hex"], m["resulting_hex"], m["delta_e"],
                m["componentes"], fecha=m.get("fecha"),
            )
