"""
utils/exporters.py
Exportación a PDF del estado actual de ColorMaster: color master y su
info derivada, los 5 gradientes, la paleta del usuario, la mezcla
sugerida (si hay) y un resumen del historial reciente.

Usa reportlab (ya en requirements.txt). No depende de PySide6, así que
es fácil de probar sin levantar la interfaz.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core import color_math as cm_color

_STYLES = getSampleStyleSheet()
_TITLE = _STYLES["Title"]
_HEADING = _STYLES["Heading2"]
_NORMAL = _STYLES["Normal"]
_SMALL = ParagraphStyle("Small", parent=_NORMAL, fontSize=8, leading=10)


def _swatch_row(hex_values: List[str], max_total_width: float = 17 * cm) -> Table:
    """Una fila de rectángulos de color con su hex debajo, como en la UI."""
    n = len(hex_values)
    cell_size = min(1.7 * cm, max_total_width / n)
    font_size = 7 if n <= 10 else (6 if n <= 14 else 5)
    label_style = ParagraphStyle("SwatchLabel", parent=_NORMAL, fontSize=font_size, leading=font_size + 1)

    color_row = [""] * n
    label_row = [Paragraph(h, label_style) for h in hex_values]

    table = Table([color_row, label_row], colWidths=[cell_size] * n)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, 0), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
        ("ROWHEIGHT", (0, 0), (-1, 0), 0.9 * cm),
        ("BOX", (0, 0), (-1, 0), 0.5, colors.HexColor("#999999")),
        ("INNERGRID", (0, 0), (-1, 0), 0.5, colors.HexColor("#999999")),
    ]
    for i, h in enumerate(hex_values):
        style.append(("BACKGROUND", (i, 0), (i, 0), colors.HexColor(h)))
    table.setStyle(TableStyle(style))
    return table


def _swatch_rows(hex_values: List[str], max_per_row: int = 14) -> List[Table]:
    """Como _swatch_row, pero si hay muchos colores (más de `max_per_row`,
    p.ej. si el usuario ha subido el nº de colores por gradiente a más de
    14) los reparte en varias filas para que el hex se siga leyendo bien."""
    n = len(hex_values)
    if n <= max_per_row:
        return [_swatch_row(hex_values)]

    import math
    num_rows = math.ceil(n / max_per_row)
    chunk_size = math.ceil(n / num_rows)
    chunks = [hex_values[i:i + chunk_size] for i in range(0, n, chunk_size)]
    return [_swatch_row(chunk) for chunk in chunks]


def _color_info_table(hex_color: str) -> Table:
    info = cm_color.ColorInfo.from_hex(hex_color)
    r, g, b = (round(v) for v in info.rgb)
    h, s, v = (round(x, 1) for x in info.hsv)
    hl, sl, l = (round(x, 1) for x in info.hsl)
    c, m, y, k = (round(x, 1) for x in info.cmyk)

    data = [
        ["", "HEX", info.hex],
        ["", "RGB", f"{r}, {g}, {b}"],
        ["", "HSV", f"{h}°, {s}%, {v}%"],
        ["", "HSL", f"{hl}°, {sl}%, {l}%"],
        ["", "CMYK", f"{c}%, {m}%, {y}%, {k}%"],
    ]
    table = Table(data, colWidths=[1.3 * cm, 1.5 * cm, 5 * cm])
    table.setStyle(TableStyle([
        ("SPAN", (0, 0), (0, -1)),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(info.hex)),
        ("BOX", (0, 0), (0, -1), 0.5, colors.HexColor("#999999")),
        ("FONTSIZE", (1, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def export_report(
    output_path: str,
    master_hex: str,
    master2_hex: Optional[str] = None,
    gradients: Optional[Dict[str, List[str]]] = None,
    palette_name: Optional[str] = None,
    palette_pigments: Optional[List[dict]] = None,
    mix_result: Optional[dict] = None,
    recent_colors: Optional[List[tuple]] = None,
    recent_mixes: Optional[List[dict]] = None,
) -> str:
    """Genera el PDF y devuelve la ruta del archivo.

    - gradients: {"Brillo": [hex,...], "Saturación": [...], ...}
    - palette_pigments: lista de dicts con nombre/marca/tipo/hex (como los
      que devuelve database.db_manager.DBManager.get_pigments()).
    - mix_result: {"target_hex", "resulting_hex", "delta_e", "componentes":[{nombre,marca,porcentaje}]}
    - recent_colors: [(hex, tipo, fecha), ...] (como utils.history.HistoryManager.get_color_history)
    - recent_mixes: [{"target_hex","resulting_hex","delta_e","componentes","fecha"}, ...]
    """
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
    )
    story = []

    story.append(Paragraph("ColorMaster — Informe de color", _TITLE))
    story.append(Paragraph(datetime.now().strftime("%Y-%m-%d %H:%M"), _SMALL))
    story.append(Spacer(1, 0.6 * cm))

    # -- color master y complementario -----------------------------------------
    story.append(Paragraph("Color master", _HEADING))
    story.append(_color_info_table(master_hex))
    story.append(Spacer(1, 0.3 * cm))

    comp = cm_color.complementary(master_hex)
    story.append(Paragraph("Complementario", _NORMAL))
    story.append(_color_info_table(comp))
    story.append(Spacer(1, 0.6 * cm))

    # -- gradientes -------------------------------------------------------------
    if gradients:
        story.append(Paragraph("Gradientes", _HEADING))
        for nombre, valores in gradients.items():
            story.append(Paragraph(nombre, _NORMAL))
            for tabla in _swatch_rows(valores):
                story.append(tabla)
                story.append(Spacer(1, 0.1 * cm))
            story.append(Spacer(1, 0.25 * cm))
        story.append(Spacer(1, 0.3 * cm))

    # -- paleta del usuario -------------------------------------------------------
    if palette_pigments:
        titulo = palette_name if palette_name else "Mi paleta"
        story.append(Paragraph(titulo, _HEADING))
        data = [["", "Nombre", "Marca", "Tipo", "Hex"]]
        for p in palette_pigments:
            data.append(["", p["nombre"], p["marca"], p["tipo"], p["hex"]])
        table = Table(data, colWidths=[0.6 * cm, 5 * cm, 3.5 * cm, 2.5 * cm, 2 * cm])
        style = [
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        for i, p in enumerate(palette_pigments, start=1):
            style.append(("BACKGROUND", (0, i), (0, i), colors.HexColor(p["hex"])))
        table.setStyle(TableStyle(style))
        story.append(table)
        story.append(Spacer(1, 0.6 * cm))

    # -- mezcla sugerida ----------------------------------------------------------
    if mix_result:
        story.append(Paragraph("Mezcla sugerida", _HEADING))
        de = mix_result["delta_e"]
        veredicto = "buena coincidencia" if de < 3 else ("aceptable" if de < 6 else "pobre")

        top_row = [["Objetivo", "", "Resultado", "", f"dE = {de:.2f} ({veredicto})"]]
        table = Table(top_row, colWidths=[2 * cm, 1.3 * cm, 2 * cm, 1.3 * cm, 5 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor(mix_result["target_hex"])),
            ("BACKGROUND", (3, 0), (3, 0), colors.HexColor(mix_result["resulting_hex"])),
            ("BOX", (1, 0), (1, 0), 0.5, colors.HexColor("#999999")),
            ("BOX", (3, 0), (3, 0), 0.5, colors.HexColor("#999999")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.2 * cm))

        for c in mix_result["componentes"]:
            story.append(Paragraph(f"• {c['porcentaje']}% {c['nombre']} ({c['marca']})", _NORMAL))
        story.append(Spacer(1, 0.6 * cm))

    # -- historial reciente ---------------------------------------------------------
    if recent_colors or recent_mixes:
        story.append(PageBreak())
        story.append(Paragraph("Historial reciente", _HEADING))

        if recent_colors:
            story.append(Paragraph("Colores", _NORMAL))
            data = [["", "Hex", "Tipo", "Fecha"]]
            for hex_color, tipo, fecha in recent_colors:
                data.append(["", hex_color, tipo, fecha])
            table = Table(data, colWidths=[0.6 * cm, 2.5 * cm, 2.5 * cm, 4 * cm])
            style = [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
            ]
            for i, (hex_color, _tipo, _fecha) in enumerate(recent_colors, start=1):
                style.append(("BACKGROUND", (0, i), (0, i), colors.HexColor(hex_color)))
            table.setStyle(TableStyle(style))
            story.append(table)
            story.append(Spacer(1, 0.4 * cm))

        if recent_mixes:
            story.append(Paragraph("Mezclas", _NORMAL))
            for m in recent_mixes:
                componentes = ", ".join(f"{c['porcentaje']}% {c['nombre']}" for c in m["componentes"])
                texto = (
                    f"{m['fecha']} — objetivo {m['target_hex']} → resultado {m['resulting_hex']} "
                    f"(dE={m['delta_e']:.2f}) — {componentes}"
                )
                story.append(Paragraph(texto, _SMALL))
            story.append(Spacer(1, 0.3 * cm))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.build(story)
    return output_path
