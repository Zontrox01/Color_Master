"""
core/color_math.py
Conversiones de color (HEX, RGB, HSV, HSL, CMYK) y generación de los
gradientes que usará la interfaz: brillo, saturación, tono, luminosidad
y transición master -> master2.

Convenciones:
- HEX: string "#RRGGBB" (mayúsculas, con '#').
- RGB: tupla de floats 0-255.
- HSV/HSL: H en grados [0, 360), S y V/L en porcentaje [0, 100].
- CMYK: porcentaje [0, 100].
"""

from __future__ import annotations

import colorsys
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Tuple

Hex = str
RGB = Tuple[float, float, float]
HSV = Tuple[float, float, float]
HSL = Tuple[float, float, float]
CMYK = Tuple[float, float, float, float]
Lab = Tuple[float, float, float]


# ---------------------------------------------------------------------------
# Conversiones básicas
# ---------------------------------------------------------------------------

def hex_to_rgb(hex_color: Hex) -> RGB:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"Código hexadecimal inválido: {hex_color}")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (float(r), float(g), float(b))


def rgb_to_hex(rgb: RGB) -> Hex:
    r, g, b = (max(0, min(255, round(c))) for c in rgb)
    return f"#{int(r):02X}{int(g):02X}{int(b):02X}"


def rgb_to_hsv(rgb: RGB) -> HSV:
    r, g, b = (c / 255.0 for c in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return (h * 360.0, s * 100.0, v * 100.0)


def hsv_to_rgb(hsv: HSV) -> RGB:
    h, s, v = hsv
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360.0, max(0, min(100, s)) / 100.0,
                                   max(0, min(100, v)) / 100.0)
    return (r * 255.0, g * 255.0, b * 255.0)


def rgb_to_hsl(rgb: RGB) -> HSL:
    r, g, b = (c / 255.0 for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return (h * 360.0, s * 100.0, l * 100.0)


def hsl_to_rgb(hsl: HSL) -> RGB:
    h, s, l = hsl
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360.0, max(0, min(100, l)) / 100.0,
                                   max(0, min(100, s)) / 100.0)
    return (r * 255.0, g * 255.0, b * 255.0)


def rgb_to_cmyk(rgb: RGB) -> CMYK:
    r, g, b = (c / 255.0 for c in rgb)
    k = 1 - max(r, g, b)
    if k >= 1.0:
        return (0.0, 0.0, 0.0, 100.0)
    c = (1 - r - k) / (1 - k)
    m = (1 - g - k) / (1 - k)
    y = (1 - b - k) / (1 - k)
    return (c * 100.0, m * 100.0, y * 100.0, k * 100.0)


def cmyk_to_rgb(cmyk: CMYK) -> RGB:
    c, m, y, k = (v / 100.0 for v in cmyk)
    r = 255.0 * (1 - c) * (1 - k)
    g = 255.0 * (1 - m) * (1 - k)
    b = 255.0 * (1 - y) * (1 - k)
    return (r, g, b)


# Atajos directos hex <-> hsv/hsl/cmyk, útiles para la UI
def hex_to_hsv(hex_color: Hex) -> HSV:
    return rgb_to_hsv(hex_to_rgb(hex_color))


def hsv_to_hex(hsv: HSV) -> Hex:
    return rgb_to_hex(hsv_to_rgb(hsv))


def hex_to_hsl(hex_color: Hex) -> HSL:
    return rgb_to_hsl(hex_to_rgb(hex_color))


def hsl_to_hex(hsl: HSL) -> Hex:
    return rgb_to_hex(hsl_to_rgb(hsl))


def hex_to_cmyk(hex_color: Hex) -> CMYK:
    return rgb_to_cmyk(hex_to_rgb(hex_color))


def cmyk_to_hex(cmyk: CMYK) -> Hex:
    return rgb_to_hex(cmyk_to_rgb(cmyk))


# ---------------------------------------------------------------------------
# Color complementario
# ---------------------------------------------------------------------------

def complementary(hex_color: Hex) -> Hex:
    """Complementario clásico: rotación de 180° en el tono (HSV), S y V iguales."""
    h, s, v = hex_to_hsv(hex_color)
    return hsv_to_hex(((h + 180) % 360, s, v))


# ---------------------------------------------------------------------------
# Gradientes de 10 pasos
# ---------------------------------------------------------------------------
# Regla acordada: el master NO tiene por qué estar en el centro. Se generan
# 10 valores repartidos linealmente entre el mínimo y el máximo del rango,
# y se localiza dónde cae el master dentro de esa distribución (se sustituye
# el paso más cercano por el valor exacto del master para que siempre esté
# representado con precisión).

def _linspace(a: float, b: float, n: int) -> List[float]:
    if n == 1:
        return [a]
    step = (b - a) / (n - 1)
    return [a + step * i for i in range(n)]


def _insert_master(values: List[float], master_value: float) -> List[float]:
    """Sustituye el valor más cercano al master por el valor exacto del master,
    manteniendo la lista ordenada y con 10 elementos."""
    closest_idx = min(range(len(values)), key=lambda i: abs(values[i] - master_value))
    values[closest_idx] = master_value
    return values


def gradient_brightness(hex_color: Hex, steps: int = 10) -> List[Hex]:
    """Gradiente sobre V (HSV) de 0 a 100, con el master en su posición real."""
    h, s, v = hex_to_hsv(hex_color)
    values = _linspace(0.0, 100.0, steps)
    values = _insert_master(values, v)
    return [hsv_to_hex((h, s, val)) for val in values]


def gradient_saturation(hex_color: Hex, steps: int = 10) -> List[Hex]:
    """Gradiente sobre S (HSV) de 0 a 100 (sustituye a 'contraste')."""
    h, s, v = hex_to_hsv(hex_color)
    values = _linspace(0.0, 100.0, steps)
    values = _insert_master(values, s)
    return [hsv_to_hex((h, val, v)) for val in values]


def gradient_hue(hex_color: Hex, steps: int = 10) -> List[Hex]:
    """Vuelta completa de tono (0-360°) alrededor del master, empezando en el master."""
    h, s, v = hex_to_hsv(hex_color)
    step_deg = 360.0 / steps
    return [hsv_to_hex(((h + step_deg * i) % 360, s, v)) for i in range(steps)]


def gradient_lightness(hex_color: Hex, steps: int = 10) -> List[Hex]:
    """Gradiente sobre L (HSL) de 0 a 100, coherente con brillo/saturación."""
    h, s, l = hex_to_hsl(hex_color)
    values = _linspace(0.0, 100.0, steps)
    values = _insert_master(values, l)
    return [hsl_to_hex((h, s, val)) for val in values]


def gradient_transition(hex_master: Hex, hex_master2: Hex, steps: int = 10) -> List[Hex]:
    """Transición lineal en RGB entre master y master2 (10 pasos, incluye ambos extremos)."""
    rgb1 = hex_to_rgb(hex_master)
    rgb2 = hex_to_rgb(hex_master2)
    result = []
    for i in range(steps):
        t = i / (steps - 1) if steps > 1 else 0
        rgb = tuple(rgb1[c] + (rgb2[c] - rgb1[c]) * t for c in range(3))
        result.append(rgb_to_hex(rgb))
    return result


@dataclass
class ColorInfo:
    """Agrupa toda la info derivada de un color master, lista para pintar en la UI."""
    hex: Hex
    rgb: RGB
    hsv: HSV
    hsl: HSL
    cmyk: CMYK
    complementary: Hex

    @classmethod
    def from_hex(cls, hex_color: Hex) -> "ColorInfo":
        rgb = hex_to_rgb(hex_color)
        return cls(
            hex=hex_color.upper(),
            rgb=rgb,
            hsv=rgb_to_hsv(rgb),
            hsl=rgb_to_hsl(rgb),
            cmyk=rgb_to_cmyk(rgb),
            complementary=complementary(hex_color),
        )


# ---------------------------------------------------------------------------
# CIE L*a*b* (D65) -> sRGB -> HEX
# Usado tanto por utils/conversor_lab_hex.py (catálogos oficiales) como por
# el diálogo de "añadir pigmento" de la UI (cuando el usuario introduce
# valores L*a*b* de una ficha técnica). No depende de 'colormath' — es la
# misma implementación manual de la fórmula de Kubelka... perdón, de la
# transformación estándar CIE, para evitar el problema de compatibilidad
# que dio esa librería.
# ---------------------------------------------------------------------------

def lab_to_rgb(L: float, a: float, b: float) -> RGB:
    """Convierte CIE L*a*b* (iluminante D65) a RGB (0-255)."""
    y = ((L + 16) / 116) ** 3 if L > 8 else L / 903.3
    fy = y ** (1 / 3) if y > 0.008856 else 7.787 * y + 16 / 116
    fx = (a / 500) + fy
    fz = fy - (b / 200)
    x = fx ** 3 if fx ** 3 > 0.008856 else (fx - 16 / 116) / 7.787
    z = fz ** 3 if fz ** 3 > 0.008856 else (fz - 16 / 116) / 7.787

    X, Y, Z = x * 95.047, y * 100.000, z * 108.883

    r = (3.2406 * X - 1.5372 * Y - 0.4986 * Z) / 100
    g = (-0.9689 * X + 1.8758 * Y + 0.0415 * Z) / 100
    b_ = (0.0557 * X - 0.2040 * Y + 1.0570 * Z) / 100

    def gamma_correct(c):
        c = max(0.0, min(1.0, c))
        return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055

    r, g, b_ = (max(0.0, min(1.0, gamma_correct(c))) for c in (r, g, b_))
    return (r * 255.0, g * 255.0, b_ * 255.0)


def lab_to_hex(L: float, a: float, b: float) -> Hex:
    return rgb_to_hex(lab_to_rgb(L, a, b))


# ---------------------------------------------------------------------------
# pigment_id estable: no cambia aunque se reordenen o añadan fabricantes.
# Se usa como clave primaria del pigmento en toda la aplicación (paleta,
# historial, mezclas). `prefix` distingue pigmentos personalizados del
# usuario (prefix="custom__") de los de catálogos oficiales (sin prefijo).
# ---------------------------------------------------------------------------

def make_pigment_id(marca: str, tipo: str, nombre: str, prefix: str = "") -> str:
    def slug(text: str) -> str:
        text = str(text).strip().lower()
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
        return text or "x"

    return f"{prefix}{slug(marca)}__{slug(tipo)}__{slug(nombre)}"
