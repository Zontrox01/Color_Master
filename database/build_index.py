"""
database/build_index.py
Regenera database/pigment_index.xlsx a partir de la lista de fuentes
declaradas aquí abajo. Ejecutar cada vez que se añada un fabricante
nuevo (un archivo <algo>_convertido.xlsx generado con
utils/conversor_lab_hex.py).

Uso:
    python database/build_index.py
"""

from pathlib import Path

import pandas as pd

DATABASE_DIR = Path(__file__).resolve().parent

# Añade aquí una entrada por cada archivo <marca>_<tipo>_convertido.xlsx
# que exista en database/. El campo "archivo" es el nombre del fichero,
# sin ruta (se asume que vive en database/).
SOURCES = [
    {"marca": "Golden", "tipo": "Acrilico", "archivo": "golden_convertido.xlsx",
     "fiabilidad": 5, "fuente": "Golden Official"},
    {"marca": "Winsor & Newton", "tipo": "Acuarela", "archivo": "winsor_acuarela_convertido.xlsx",
     "fiabilidad": 5, "fuente": "Winsor & Newton Official"},
    {"marca": "Winsor & Newton", "tipo": "Oleo", "archivo": "winsor_oleo_convertido.xlsx",
     "fiabilidad": 5, "fuente": "Winsor & Newton Official"},
    {"marca": "Schmincke", "tipo": "Acuarela", "archivo": "schmincke_convertido.xlsx",
     "fiabilidad": 4, "fuente": "Schmincke Official"},
]


def build_index(output_path: Path = DATABASE_DIR / "pigment_index.xlsx") -> pd.DataFrame:
    rows = []
    for s in SOURCES:
        file_path = DATABASE_DIR / s["archivo"]
        if not file_path.exists():
            print(f"⚠️  Aviso: no existe {file_path}, se omite del índice.")
            continue
        df = pd.read_excel(file_path)
        if "pigment_id" not in df.columns:
            print(f"⚠️  Aviso: {s['archivo']} no tiene columna 'pigment_id' (regenéralo "
                  f"con la versión actual de utils/conversor_lab_hex.py), se omite.")
            continue
        rows.append({**s, "num_colores": len(df)})

    index_df = pd.DataFrame(rows)[["marca", "tipo", "archivo", "num_colores", "fiabilidad", "fuente"]]
    index_df.to_excel(output_path, index=False, sheet_name="Indice")
    print(f"✅ Índice guardado en {output_path} ({len(index_df)} fuentes)")
    return index_df


if __name__ == "__main__":
    build_index()
