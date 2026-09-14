"""
core/mixer.py
Modelo de mezcla de pigmentos y optimizador de proporciones.

No disponemos de reflectancia espectral real de los pigmentos (solo
L*a*b*/hex y opacidad), así que en vez de Kubelka-Munk "de verdad"
usamos una aproximación muy extendida cuando falta el espectro:
Kubelka-Munk de constante única aplicado a cada canal R, G, B por
separado, tratándolos como tres bandas espectrales anchas. Esto se
comporta de forma mucho más parecida a mezclar pigmentos reales que
promediar RGB directamente (amarillo + azul tiende a verde, no a gris).

La opacidad de cada pigmento pondera su "fuerza" en la mezcla: un
pigmento transparente aporta menos color por unidad de proporción que
uno opaco, de forma similar a cómo se comportan acuarelas vs. acrílicos.

Referencias del método (aproximación, no exacta):
- Kubelka, P.; Munk, F. "Ein Beitrag zur Optik der Farbanstriche" (1931).
- Aplicación de constante única por canal: técnica común en simuladores
  de mezcla de pigmentos que solo disponen de RGB (p. ej. la lógica
  detrás de herramientas como Mixbox usa un enfoque más sofisticado con
  datos precalculados; aquí usamos la variante simple sin esos datos).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from core import color_math as cm

RGB01 = Tuple[float, float, float]  # canales en [0, 1]


# ---------------------------------------------------------------------------
# Kubelka-Munk de constante única, por canal
# ---------------------------------------------------------------------------

_EPS = 1e-6


def _rgb_to_unit(rgb: cm.RGB) -> RGB01:
    return tuple(max(_EPS, min(1.0, c / 255.0)) for c in rgb)


def _unit_to_rgb(rgb01: RGB01) -> cm.RGB:
    return tuple(max(0.0, min(255.0, c * 255.0)) for c in rgb01)


def _r_to_ks(r: float) -> float:
    """K/S a partir de la reflectancia (fórmula de Kubelka-Munk)."""
    r = max(_EPS, min(1.0 - _EPS, r))
    return ((1 - r) ** 2) / (2 * r)


def _ks_to_r(ks: float) -> float:
    """Reflectancia a partir de K/S (inversa de Kubelka-Munk)."""
    ks = max(0.0, ks)
    return 1 + ks - (ks ** 2 + 2 * ks) ** 0.5


def hex_to_ks(hex_color: cm.Hex) -> Tuple[float, float, float]:
    r, g, b = _rgb_to_unit(cm.hex_to_rgb(hex_color))
    return (_r_to_ks(r), _r_to_ks(g), _r_to_ks(b))


def ks_to_hex(ks: Tuple[float, float, float]) -> cm.Hex:
    r, g, b = (_ks_to_r(v) for v in ks)
    return cm.rgb_to_hex(_unit_to_rgb((r, g, b)))


@dataclass
class Pigment:
    """Vista mínima de un pigmento, ya sea recién cargado desde el Excel de
    un fabricante o reconstruido desde la paleta guardada del usuario."""

    id: str  # pigment_id estable (marca__tipo__nombre normalizado)
    marca: str
    tipo: str
    nombre: str
    hex: cm.Hex
    opacidad: float = 1.0

    @classmethod
    def from_row(cls, row: dict) -> "Pigment":
        # Los Excel por fabricante usan 'Nombre'/'Tipo'/'Opacidad' (tal como
        # los genera utils/conversor_lab_hex.py); la paleta del usuario en
        # SQLite usa minúsculas. Buscamos sin distinguir mayúsculas.
        def get(*keys, default=None):
            lower_map = {str(k).lower(): v for k, v in row.items()}
            for k in keys:
                if k.lower() in lower_map and pd_notna(lower_map[k.lower()]):
                    return lower_map[k.lower()]
            return default

        pigment_id = get("pigment_id", "id")
        marca = get("marca", default="")
        tipo = get("tipo", default="")
        nombre = get("nombre", default="")
        if not pigment_id:
            # Compatibilidad hacia atrás por si llega una fila sin pigment_id
            pigment_id = f"{marca}__{tipo}__{nombre}".lower().replace(" ", "_")

        return cls(
            id=str(pigment_id),
            marca=str(marca),
            tipo=str(tipo),
            nombre=str(nombre),
            hex=str(get("hex", default="#000000")),
            opacidad=float(get("opacidad", default=1.0) or 1.0),
        )


def pd_notna(value) -> bool:
    """Evita importar pandas aquí solo para un chequeo de NaN."""
    try:
        return value == value and value is not None  # NaN != NaN
    except Exception:
        return value is not None


def mix_pigments(components: Sequence[Tuple[Pigment, float]]) -> cm.Hex:
    """Mezcla pigmentos con sus proporciones (deben sumar ~1.0).

    Cada pigmento pesa en la mezcla según proporción * opacidad, de forma
    que un pigmento muy transparente influye menos por unidad de proporción.
    """
    weighted_ks = [0.0, 0.0, 0.0]
    total_weight = 0.0

    for pigment, proportion in components:
        if proportion <= 0:
            continue
        weight = proportion * max(0.05, pigment.opacidad)  # nunca 0 del todo
        ks = hex_to_ks(pigment.hex)
        for i in range(3):
            weighted_ks[i] += ks[i] * weight
        total_weight += weight

    if total_weight <= 0:
        return "#FFFFFF"

    avg_ks = tuple(v / total_weight for v in weighted_ks)
    return ks_to_hex(avg_ks)


# ---------------------------------------------------------------------------
# Delta E (CIE76, distancia euclídea en Lab) — aproximado pero suficiente
# para dar una idea de "qué tan cerca" está la mezcla del objetivo.
# ---------------------------------------------------------------------------

def _hex_to_lab(hex_color: cm.Hex) -> Tuple[float, float, float]:
    # Reutilizamos el mismo camino que usa el conversor de la base de datos
    # (D65) pero en sentido inverso: aquí solo necesitamos L*a*b* a partir
    # de sRGB, así que usamos la conversión estándar sRGB -> XYZ -> Lab.
    r, g, b = _rgb_to_unit(cm.hex_to_rgb(hex_color))

    def inv_gamma(c):
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92

    r, g, b = inv_gamma(r), inv_gamma(g), inv_gamma(b)

    X = (r * 0.4124 + g * 0.3576 + b * 0.1805) * 100
    Y = (r * 0.2126 + g * 0.7152 + b * 0.0722) * 100
    Z = (r * 0.0193 + g * 0.1192 + b * 0.9505) * 100

    Xn, Yn, Zn = 95.047, 100.0, 108.883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)

    fx, fy, fz = f(X / Xn), f(Y / Yn), f(Z / Zn)
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b_ = 200 * (fy - fz)
    return (L, a, b_)


def delta_e76(hex_a: cm.Hex, hex_b: cm.Hex) -> float:
    L1, a1, b1 = _hex_to_lab(hex_a)
    L2, a2, b2 = _hex_to_lab(hex_b)
    return ((L1 - L2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2) ** 0.5


# ---------------------------------------------------------------------------
# Optimizador de mezcla: preselección + búsqueda basta -> fina
# ---------------------------------------------------------------------------

@dataclass
class MixResult:
    components: List[Tuple[Pigment, float]]  # (pigmento, proporción 0-1)
    resulting_hex: cm.Hex
    delta_e: float

    def as_percentages(self) -> List[Tuple[Pigment, float]]:
        return [(p, round(prop * 100, 1)) for p, prop in self.components]


def _compositions(n_parts: int, step: int) -> List[Tuple[int, ...]]:
    """Genera todas las combinaciones de n_parts enteros no negativos que
    suman 100, en múltiplos de `step` (ej.: step=10 -> 0,10,20...100)."""
    units = 100 // step
    results = []

    def helper(remaining_units, remaining_parts, current):
        if remaining_parts == 1:
            results.append(tuple(current + [remaining_units]))
            return
        for u in range(remaining_units + 1):
            helper(remaining_units - u, remaining_parts - 1, current + [u])

    helper(units, n_parts, [])
    return [tuple(u * step for u in combo) for combo in results]


def _best_proportion_for_combo(
    target_hex: cm.Hex, pigments: Sequence[Pigment], coarse_step: int, fine_step: int
) -> Tuple[List[float], cm.Hex, float]:
    """Búsqueda en dos fases: rejilla basta y luego refinamiento alrededor
    del mejor punto encontrado."""
    n = len(pigments)
    if n == 1:
        mixed = pigments[0].hex
        return [1.0], mixed, delta_e76(target_hex, mixed)

    best_combo, best_hex, best_de = None, None, float("inf")
    for combo in _compositions(n, coarse_step):
        proportions = [c / 100.0 for c in combo]
        if sum(1 for p in proportions if p > 0) < 2:
            continue  # evitar combos degenerados (solo 1 pigmento activo)
        mixed = mix_pigments(list(zip(pigments, proportions)))
        de = delta_e76(target_hex, mixed)
        if de < best_de:
            best_combo, best_hex, best_de = combo, mixed, de

    if best_combo is None:
        return [1.0 / n] * n, mix_pigments([(p, 1.0 / n) for p in pigments]), float("inf")

    # Refinamiento: rejilla fina alrededor del mejor combo basto
    lo = [max(0, c - coarse_step) for c in best_combo]
    hi = [min(100, c + coarse_step) for c in best_combo]

    def helper(idx, remaining, current):
        nonlocal best_combo, best_hex, best_de
        if idx == n - 1:
            val = remaining
            if lo[idx] <= val <= hi[idx]:
                combo = tuple(current + [val])
                proportions = [c / 100.0 for c in combo]
                mixed = mix_pigments(list(zip(pigments, proportions)))
                de = delta_e76(target_hex, mixed)
                if de < best_de:
                    best_combo, best_hex, best_de = combo, mixed, de
            return
        start = max(0, lo[idx])
        end = min(remaining, hi[idx])
        for v in range(start, end + 1, fine_step):
            helper(idx + 1, remaining - v, current + [v])

    helper(0, 100, [])
    return [c / 100.0 for c in best_combo], best_hex, best_de


def suggest_mix(
    target_hex: cm.Hex,
    available_pigments: Sequence[Pigment],
    max_pigments: int = 4,
    top_n_candidates: int = 8,
    coarse_step: int = 10,
    fine_step: int = 2,
) -> Optional[MixResult]:
    """Busca la combinación de hasta `max_pigments` pigmentos (de entre los
    disponibles) que mejor aproxima `target_hex`.

    Estrategia (para que sea rápido incluso con paletas grandes):
    1. Preselecciona los `top_n_candidates` pigmentos individualmente más
       cercanos al objetivo (por Delta E).
    2. Prueba todas las combinaciones de tamaño 1..max_pigments dentro de
       esa preselección.
    3. Para cada combinación, busca la mejor proporción en dos fases
       (rejilla basta -> refinamiento fino).
    """
    if not available_pigments:
        return None

    ranked = sorted(available_pigments, key=lambda p: delta_e76(target_hex, p.hex))
    candidates = ranked[:top_n_candidates]

    best_result: Optional[MixResult] = None

    for size in range(1, min(max_pigments, len(candidates)) + 1):
        for combo in itertools.combinations(candidates, size):
            proportions, mixed_hex, de = _best_proportion_for_combo(
                target_hex, combo, coarse_step, fine_step
            )
            if best_result is None or de < best_result.delta_e:
                components = [(p, prop) for p, prop in zip(combo, proportions) if prop > 0]
                best_result = MixResult(components=components, resulting_hex=mixed_hex, delta_e=de)

    return best_result
