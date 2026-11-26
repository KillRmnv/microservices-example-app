"""Folk landmark gazetteer used to resolve "near X" phrases.

Nominatim is not reachable from the cluster, so a small curated gazetteer
covers the common meeting points. Matching uses a five-letter stem so
inflections (Немига/Немиги/Немиге) resolve to the same point.
"""
from __future__ import annotations

from . import i18n

LANDMARKS: dict[str, tuple[float, float]] = {
    "немига": (53.9056, 27.5539),
    "троицкое предместье": (53.9083, 27.5566),
    "троицкое": (53.9083, 27.5566),
    "парк челюскинцев": (53.9247, 27.6136),
    "парк горького": (53.9036, 27.5716),
    "октябрьская площадь": (53.9028, 27.5618),
    "ст. м. октябрьская": (53.9028, 27.5618),
    "ст м октябрьская": (53.9028, 27.5618),
    "октябрьская": (53.9028, 27.5618),
    "площадь победы": (53.9085, 27.5746),
    "верхний город": (53.9025, 27.5546),
    "комаровка": (53.9167, 27.5803),
    "минск-арена": (53.9431, 27.4822),
    "дворец республики": (53.9028, 27.5618),
    "дворец спорта": (53.9342, 27.5540),
    "ботанический сад": (53.9167, 27.6136),
    "лошицкий парк": (53.8500, 27.6200),
}


def resolve_location(query: str | None, city: str,
                     center: tuple[float, float],
                     language: str | None = None) -> dict:
    """Landmark coordinates or the configured city center as a fallback."""
    if query:
        normalized = query.strip().casefold()
        for name, coords in LANDMARKS.items():
            stem = name[:5] if len(name) >= 5 else name
            if stem and (stem in normalized or normalized in name):
                return {"lat": coords[0], "lon": coords[1],
                        "label": query.strip(), "city": city}
    return {
        "lat": center[0],
        "lon": center[1],
        "label": i18n.t("geo_center", language, city=city),
        "city": city,
    }
