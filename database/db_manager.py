"""
database/db_manager.py
Persistencia de las paletas del usuario en SQLite (independiente de
pigment_data.xlsx, que es la base de datos maestra de fabricantes).

Esquema:
    palettes(id, nombre, fecha_creacion)
    paleta_pigmentos(paleta_id, pigmento_id, cantidad_aproximada)
        -> pigmento_id referencia el 'id' de pigment_data.xlsx

No depende de PySide6: es una capa de datos pura, fácil de probar sin
levantar la interfaz.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple

DB_PATH = Path(__file__).resolve().parent / "user_palettes" / "user_palette.db"

DEFAULT_PALETTE_NAME = "Mi paleta"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS palettes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE NOT NULL,
    fecha_creacion TEXT NOT NULL
);

-- Los datos del pigmento se guardan aquí de forma autocontenida
-- (marca, tipo, nombre, hex, opacidad), NO solo una referencia a un id.
-- Esto es intencional: permite mostrar la paleta del usuario y calcular
-- mezclas sin tener que volver a cargar el Excel del fabricante de
-- origen. Solo se necesita el archivo del fabricante cuando el usuario
-- quiere *explorar* nuevos pigmentos para añadir a su paleta.
CREATE TABLE IF NOT EXISTS paleta_pigmentos (
    paleta_id INTEGER NOT NULL,
    pigmento_id TEXT NOT NULL,       -- pigment_id estable (ver conversor_lab_hex.py)
    marca TEXT NOT NULL,
    tipo TEXT NOT NULL,
    nombre TEXT NOT NULL,
    hex TEXT NOT NULL,
    opacidad REAL NOT NULL DEFAULT 1.0,
    cantidad_aproximada TEXT,
    fecha_anadido TEXT NOT NULL,
    PRIMARY KEY (paleta_id, pigmento_id),
    FOREIGN KEY (paleta_id) REFERENCES palettes(id) ON DELETE CASCADE
);

-- Pigmentos que el usuario añade a mano: un fabricante nuevo, o una
-- tinta nueva para un fabricante ya existente en los catálogos oficiales.
-- Independiente de las paletas: es "base de datos" del usuario, no
-- pertenece a ninguna paleta en concreto (se puede añadir a cualquiera
-- igual que un pigmento de catálogo oficial).
CREATE TABLE IF NOT EXISTS pigmentos_personalizados (
    pigment_id TEXT PRIMARY KEY,
    marca TEXT NOT NULL,
    tipo TEXT NOT NULL,
    nombre TEXT NOT NULL,
    hex TEXT NOT NULL,
    opacidad REAL NOT NULL DEFAULT 1.0,
    fiabilidad INTEGER NOT NULL DEFAULT 2,
    fuente TEXT NOT NULL DEFAULT 'Introducido manualmente por el usuario',
    fecha_creacion TEXT NOT NULL
);
"""


class DBManager:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
        self._migrate_if_needed()

    def _migrate_if_needed(self):
        """Si existe una paleta_pigmentos de una versión anterior (sin las
        columnas marca/tipo/nombre/hex/opacidad autocontenidas), la
        reemplaza por el esquema nuevo. No hay forma de recuperar los
        pigmentos antiguos sin volver a los Excel de origen, así que se
        pierden — asumible en esta fase de desarrollo."""
        with self._connect() as conn:
            cur = conn.execute("PRAGMA table_info(paleta_pigmentos)")
            columns = {row[1] for row in cur.fetchall()}
            required = {"marca", "tipo", "nombre", "hex", "opacidad", "fecha_anadido"}
            if not required.issubset(columns):
                conn.execute("DROP TABLE IF EXISTS paleta_pigmentos")
                conn.executescript(_SCHEMA)

    # -- paletas ------------------------------------------------------------

    def list_palettes(self) -> List[Tuple[int, str, str]]:
        """Devuelve [(id, nombre, fecha_creacion), ...] ordenadas por nombre."""
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT id, nombre, fecha_creacion FROM palettes ORDER BY nombre"
            )
            return cur.fetchall()

    def create_palette(self, nombre: str) -> int:
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("El nombre de la paleta no puede estar vacío")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO palettes (nombre, fecha_creacion) VALUES (?, ?)",
                (nombre, datetime.now().isoformat(timespec="seconds")),
            )
            return cur.lastrowid

    def get_or_create_default_palette(self) -> Tuple[int, str]:
        palettes = self.list_palettes()
        if palettes:
            return palettes[0][0], palettes[0][1]
        new_id = self.create_palette(DEFAULT_PALETTE_NAME)
        return new_id, DEFAULT_PALETTE_NAME

    def rename_palette(self, paleta_id: int, nuevo_nombre: str):
        nuevo_nombre = nuevo_nombre.strip()
        if not nuevo_nombre:
            raise ValueError("El nombre de la paleta no puede estar vacío")
        with self._connect() as conn:
            conn.execute(
                "UPDATE palettes SET nombre = ? WHERE id = ?", (nuevo_nombre, paleta_id)
            )

    def delete_palette(self, paleta_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM palettes WHERE id = ?", (paleta_id,))

    # -- pigmentos dentro de una paleta ------------------------------------------

    def get_pigment_ids(self, paleta_id: int) -> Set[str]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT pigmento_id FROM paleta_pigmentos WHERE paleta_id = ?",
                (paleta_id,),
            )
            return {row[0] for row in cur.fetchall()}

    def get_pigments(self, paleta_id: int) -> List[dict]:
        """Todos los pigmentos guardados en una paleta, con sus datos
        completos (no hace falta ningún Excel de fabricante para esto)."""
        with self._connect() as conn:
            cur = conn.execute(
                """SELECT pigmento_id, marca, tipo, nombre, hex, opacidad, cantidad_aproximada
                   FROM paleta_pigmentos WHERE paleta_id = ? ORDER BY marca, nombre""",
                (paleta_id,),
            )
            cols = ["pigment_id", "marca", "tipo", "nombre", "hex", "opacidad", "cantidad_aproximada"]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def add_pigment(
        self,
        paleta_id: int,
        pigment_id: str,
        marca: str,
        tipo: str,
        nombre: str,
        hex_color: str,
        opacidad: float = 1.0,
        cantidad_aproximada: Optional[str] = None,
    ):
        """Guarda un pigmento en la paleta con todos sus datos, de forma
        que luego no haga falta releer el Excel del fabricante."""
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO paleta_pigmentos
                   (paleta_id, pigmento_id, marca, tipo, nombre, hex, opacidad,
                    cantidad_aproximada, fecha_anadido)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    paleta_id, pigment_id, marca, tipo, nombre, hex_color, opacidad,
                    cantidad_aproximada, datetime.now().isoformat(timespec="seconds"),
                ),
            )

    def remove_pigment(self, paleta_id: int, pigment_id: str):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM paleta_pigmentos WHERE paleta_id = ? AND pigmento_id = ?",
                (paleta_id, pigment_id),
            )

    def set_pigments(self, paleta_id: int, pigments: List[dict]):
        """Reemplaza de golpe todos los pigmentos de una paleta. Cada dict
        debe tener al menos: pigment_id, marca, tipo, nombre, hex, opacidad."""
        with self._connect() as conn:
            conn.execute("DELETE FROM paleta_pigmentos WHERE paleta_id = ?", (paleta_id,))
            now = datetime.now().isoformat(timespec="seconds")
            conn.executemany(
                """INSERT INTO paleta_pigmentos
                   (paleta_id, pigmento_id, marca, tipo, nombre, hex, opacidad,
                    cantidad_aproximada, fecha_anadido)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        paleta_id, p["pigment_id"], p["marca"], p["tipo"], p["nombre"],
                        p["hex"], p.get("opacidad", 1.0), p.get("cantidad_aproximada"), now,
                    )
                    for p in pigments
                ],
            )

    # -- pigmentos personalizados (fabricantes/tintas añadidos por el usuario) ------

    def add_custom_pigment(
        self,
        pigment_id: str,
        marca: str,
        tipo: str,
        nombre: str,
        hex_color: str,
        opacidad: float = 1.0,
        fiabilidad: int = 2,
        fuente: str = "Introducido manualmente por el usuario",
    ):
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO pigmentos_personalizados
                   (pigment_id, marca, tipo, nombre, hex, opacidad, fiabilidad, fuente, fecha_creacion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pigment_id, marca, tipo, nombre, hex_color, opacidad, fiabilidad,
                    fuente, datetime.now().isoformat(timespec="seconds"),
                ),
            )

    def pigment_id_exists(self, pigment_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT 1 FROM pigmentos_personalizados WHERE pigment_id = ?", (pigment_id,)
            )
            return cur.fetchone() is not None

    def list_custom_pigments(self, marca: Optional[str] = None, tipo: Optional[str] = None) -> List[dict]:
        query = """SELECT pigment_id, marca, tipo, nombre, hex, opacidad, fiabilidad, fuente
                   FROM pigmentos_personalizados"""
        conditions, params = [], []
        if marca is not None:
            conditions.append("marca = ?")
            params.append(marca)
        if tipo is not None:
            conditions.append("tipo = ?")
            params.append(tipo)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY nombre"

        cols = ["pigment_id", "marca", "tipo", "nombre", "hex", "opacidad", "fiabilidad", "fuente"]
        with self._connect() as conn:
            cur = conn.execute(query, params)
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def list_custom_catalogs(self) -> List[Tuple[str, str, int]]:
        """Devuelve [(marca, tipo, num_colores), ...] agrupado — para
        mostrarlos en el desplegable de 'Explorar catálogo' junto a los
        oficiales."""
        with self._connect() as conn:
            cur = conn.execute(
                """SELECT marca, tipo, COUNT(*) FROM pigmentos_personalizados
                   GROUP BY marca, tipo ORDER BY marca, tipo"""
            )
            return cur.fetchall()

    def delete_custom_pigment(self, pigment_id: str):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM pigmentos_personalizados WHERE pigment_id = ?", (pigment_id,)
            )
