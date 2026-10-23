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
