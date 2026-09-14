"""
Conversor de color CIE L*a*b* a Hexadecimal
Herramienta para convertir datos de color de fabricantes a formato hexadecimal.
No depende de colormath: implementa Lab -> XYZ -> sRGB con el iluminante D65.

Uso:
    python conversor_lab_hex.py --input datos_golden.csv --output golden_convertido.xlsx --fuente "Golden" --fiabilidad 5
    python conversor_lab_hex.py --help para más opciones
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.color_math import lab_to_hex, make_pigment_id  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class LabDataHelper:
    """Utilidades de parseo/validación de los datos de entrada (CSV/Excel).
    La conversión Lab->hex en sí vive en core/color_math.py."""

    @staticmethod
    def parse_number(value):
        """Convierte un valor a float manejando comas decimales y espacios."""
        if pd.isna(value):
            return None
        try:
            str_val = str(value).strip().replace(",", ".").replace(" ", "")
            return float(str_val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def validate_lab_data(df, columns):
        errors, warnings = [], []
        for col in columns:
            if col not in df.columns:
                errors.append(f"Columna '{col}' no encontrada")
                continue
            if not pd.api.types.is_numeric_dtype(df[col]):
                warnings.append(f"Columna '{col}' no es numérica, se intentará convertir")
                try:
                    df[col] = df[col].apply(LabDataHelper.parse_number)
                except Exception:
                    errors.append(f"No se pudo convertir la columna '{col}' a números")
                    continue
            if col == "L":
                invalid = df[(df[col] < 0) | (df[col] > 100)][col].count()
                if invalid:
                    warnings.append(f"{invalid} valores de L fuera de rango (0-100)")
            if col in ("a", "b"):
                invalid = df[(df[col] < -128) | (df[col] > 128)][col].count()
                if invalid:
                    warnings.append(f"{invalid} valores de {col} fuera de rango (-128 a 128)")
        return errors, warnings


class DataSource:
    @staticmethod
    def detect_format(file_path):
        extension = Path(file_path).suffix.lower()
        if extension == ".csv":
            return "csv"
        elif extension in (".xlsx", ".xls"):
            return "excel"
        raise ValueError(f"Formato de archivo no soportado: {extension}")

    @staticmethod
    def load_data(file_path):
        format_type = DataSource.detect_format(file_path)
        if format_type == "csv":
            for delimiter in (",", ";", "\t"):
                try:
                    df = pd.read_csv(file_path, delimiter=delimiter, encoding="utf-8")
                    if len(df.columns) > 1:
                        logging.info(f"Delimitador detectado: '{delimiter}'")
                        return df
                except Exception:
                    continue
            return pd.read_csv(file_path, encoding="utf-8")
        elif format_type == "excel":
            excel_file = pd.ExcelFile(file_path)
            sheet_name = excel_file.sheet_names[0]
            return pd.read_excel(file_path, sheet_name=sheet_name)


def main():
    parser = argparse.ArgumentParser(
        description="Convierte datos CIE L*a*b* a códigos hexadecimales",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python conversor_lab_hex.py --input datos_golden.csv --output golden_convertido.xlsx
  python conversor_lab_hex.py --input datos_golden.csv --output golden_convertido.xlsx --cols L a b
  python conversor_lab_hex.py --input datos_golden.csv --validate-only
        """,
    )
    parser.add_argument("--input", "-i", required=True, help="Archivo de entrada (CSV o Excel)")
    parser.add_argument("--output", "-o", help="Archivo de salida (Excel)")
    parser.add_argument("--cols", "-c", nargs=3, default=["L", "a", "b"], help="Columnas L, a, b")
    parser.add_argument("--hex_col", "-x", default="hex", help="Columna para HEX (default: hex)")
    parser.add_argument("--validate-only", action="store_true", help="Solo valida, no convierte")
    parser.add_argument("--fiabilidad", type=int, default=5, choices=range(1, 6), help="Fiabilidad 1-5")
    parser.add_argument("--fuente", default="Fuente no especificada", help="Fuente de los datos")
    parser.add_argument("--marca", default=None, help="Marca del fabricante (si no está en el CSV)")

    args = parser.parse_args()

    logging.info(f"Cargando datos desde: {args.input}")
    try:
        df = DataSource.load_data(args.input)
        if df is None or df.empty:
            raise Exception("El archivo está vacío o no se pudo leer")
        logging.info(f"Datos cargados: {len(df)} filas, {len(df.columns)} columnas")
        logging.info(f"Columnas encontradas: {', '.join(df.columns)}")
    except Exception as e:
        logging.error(f"Error cargando archivo: {e}")
        return 1

    L_col, a_col, b_col = args.cols
    for col in (L_col, a_col, b_col):
        if col in df.columns:
            df[col] = df[col].apply(LabDataHelper.parse_number)

    errors, warnings = LabDataHelper.validate_lab_data(df, [L_col, a_col, b_col])
    if errors:
        logging.error("Errores de validación:")
        for e in errors:
            logging.error(f"  - {e}")
        return 1
    for w in warnings:
        logging.warning(w)

    if args.validate_only:
        logging.info("Validación completada. No se realizó la conversión.")
        return 0

    if not args.output:
        logging.error("Se requiere --output para realizar la conversión")
        return 1

    logging.info("Iniciando conversión Lab → HEX...")
    hex_values, errors_list = [], []
    for idx, row in df.iterrows():
        L, a, b = row[L_col], row[a_col], row[b_col]
        if pd.isna(L) or pd.isna(a) or pd.isna(b):
            errors_list.append(f"Fila {idx}: valor nulo en Lab")
            hex_values.append(None)
            continue
        hex_values.append(lab_to_hex(L, a, b))

    df[args.hex_col] = hex_values
    df["fiabilidad"] = args.fiabilidad
    df["fuente"] = args.fuente
    if args.marca and "marca" not in df.columns:
        df["marca"] = args.marca
    df["fecha_conversion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    marca_col = "marca" if "marca" in df.columns else None
    tipo_col = next((c for c in ("Tipo", "tipo") if c in df.columns), None)
    nombre_col = next((c for c in ("Nombre", "nombre") if c in df.columns), None)
    if marca_col and tipo_col and nombre_col:
        df["pigment_id"] = [
            make_pigment_id(row[marca_col], row[tipo_col], row[nombre_col])
            for _, row in df.iterrows()
        ]
        # pigment_id va primero: es la clave que usará el resto de la app
        cols = ["pigment_id"] + [c for c in df.columns if c != "pigment_id"]
        df = df[cols]
    else:
        logging.warning(
            "No se pudo generar 'pigment_id' (faltan columnas marca/tipo/nombre). "
            "Este archivo no debería usarse todavía en la aplicación."
        )

    logging.info(f"Guardando resultados en: {args.output}")
    try:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(args.output, index=False, sheet_name="Pigmentos")
        valid_hex = df[args.hex_col].notna().sum()
        invalid_hex = df[args.hex_col].isna().sum()
        logging.info(f"✅ Conversión completada. {len(df)} colores procesados.")
        logging.info(f"   HEX válidos: {valid_hex} | HEX inválidos: {invalid_hex}")
        if errors_list:
            logging.warning(f"Errores en {len(errors_list)} filas (primeras 5):")
            for e in errors_list[:5]:
                logging.warning(f"  - {e}")
        logging.info(f"📁 Archivo guardado en: {Path(args.output).absolute()}")
    except Exception as e:
        logging.error(f"Error guardando archivo: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
