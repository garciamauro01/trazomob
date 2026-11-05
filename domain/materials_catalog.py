# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Catálogo centralizado de materiais e texturas de MDF e Marmoraria do TrazoMob."""
from __future__ import annotations

from pathlib import Path

# Lista oficial de padrões de MDF disponíveis para caixas, frentes e componentes
MDF_MATERIALS = [
    "MDF Branco TX",
    "MDF Autentic Arauco",
    "MDF Carvalho",
    "MDF Castanho",
    "MDF Ciliegio Florença",
    "MDF Louro Freijó",
    "MDF Carvalho Boreal",
    "MDF Grafite",
    "MDF Cinza Sagrado",
]

# Materiais de pedras e bancadas
STONE_MATERIALS = [
    "Granito Preto São Gabriel 20mm",
    "Granito Preto Absoluto 20mm",
    "Mármore Nero Marquina 20mm",
    "Mármore Pietra Grey 20mm",
    "Quartzo Branco Calacatta 20mm",
    "Granito Branco Siena 20mm",
    "Mármore Armani Gris 20mm",
    "Mármore Branco Paraná 20mm",
    "Granito Cinza Corumbá 20mm",
]

# Combinação completa para combos gerais de material de caixa/módulo
ALL_BOX_MATERIALS = MDF_MATERIALS + STONE_MATERIALS


def get_available_mdf_materials() -> list[str]:
    """Retorna a lista de padrões de MDF."""
    return list(MDF_MATERIALS)


def get_available_stone_materials() -> list[str]:
    """Retorna a lista de padrões de pedras e bancadas."""
    return list(STONE_MATERIALS)


def get_all_materials() -> list[str]:
    """Retorna todos os materiais suportados."""
    return list(ALL_BOX_MATERIALS)


def get_material_color(material: str) -> tuple[float, float, float]:
    """Retorna a cor RGB normalizada (0.0 a 1.0) para um determinado acabamento ou padrão de material."""
    mat_lower = (material or "").lower()
    # Materiais de Marmoraria / Pedras / Metais
    if "sao gabriel" in mat_lower or "preto absoluto" in mat_lower or "granito preto" in mat_lower:
        return (0.12, 0.12, 0.13)
    if "nero" in mat_lower or "marquina" in mat_lower:
        return (0.10, 0.10, 0.11)
    if "pietra" in mat_lower or "grey" in mat_lower:
        return (0.32, 0.33, 0.35)
    if "armani" in mat_lower or "gris" in mat_lower:
        return (0.42, 0.38, 0.35)
    if "siena" in mat_lower or "branco siena" in mat_lower:
        return (0.88, 0.88, 0.86)
    if "calacatta" in mat_lower or "calacata" in mat_lower or "carrara" in mat_lower or "parana" in mat_lower:
        return (0.93, 0.93, 0.94)
    if "quartzo" in mat_lower or "silestone" in mat_lower:
        return (0.95, 0.95, 0.95)
    if "corumba" in mat_lower or "cinza andorinha" in mat_lower:
        return (0.58, 0.58, 0.59)
    if "inox" in mat_lower or "aco" in mat_lower or "aço" in mat_lower:
        return (0.80, 0.82, 0.84)
    if "cuba" in mat_lower:
        return (0.75, 0.77, 0.80)
    # MDF / Marcenaria
    if "autentic" in mat_lower:
        return (198 / 255.0, 165 / 255.0, 127 / 255.0)
    if "ciliegio" in mat_lower or "florenca" in mat_lower:
        return (206 / 255.0, 190 / 255.0, 171 / 255.0)
    if "castanho" in mat_lower:
        return (100 / 255.0, 74 / 255.0, 54 / 255.0)
    if "carvalho" in mat_lower:
        return (203 / 255.0, 175 / 255.0, 142 / 255.0)
    if "freijo" in mat_lower or "madeira" in mat_lower:
        return (0.75, 0.55, 0.35)
    if "grafite" in mat_lower or "preto" in mat_lower or "chumbo" in mat_lower:
        return (0.25, 0.25, 0.25)
    if "cinza" in mat_lower or "titanio" in mat_lower:
        return (0.65, 0.65, 0.65)
    return (0.95, 0.95, 0.93)
