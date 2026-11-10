# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
import pytest
from plugins.trazomob.builders.frentes import FrentesKitBuilder
from plugins.trazomob.builders.chapa_spec import ModuloMaterialContext


def test_kit_portas_giro_dimensoes_e_folgas():
    # Balcão de 800mm de largura x 700mm de altura, 2 portas
    ctx = ModuloMaterialContext(
        material_frentes="MDF Carvalho 18mm",
    )
    portas = FrentesKitBuilder.build_kit_portas_giro(
        largura_total_m=0.800,
        altura_total_m=0.700,
        num_portas=2,
        origin=(0.0, 0.0, 0.0),
        esp_frente_m=0.018,
        ctx=ctx,
        prefixo="Balcao Teste",
    )
    assert len(portas) == 2
    p_esq, p_dir = portas

    # Verifica nomes
    assert "Porta Esq" in p_esq.name
    assert "Porta Dir" in p_dir.name

    # Folga perimetro = 3mm em cada ponta -> largura total disponível = 800 - 6 - 3 (folga centro) = 791mm / 2 = 395.5mm
    meta_esq = p_esq.ext["trazomob"]
    meta_dir = p_dir.ext["trazomob"]
    assert meta_esq["material"] == "MDF Carvalho 18mm"
    assert round(meta_esq["largura"], 1) == 395.5 or round(meta_esq["comprimento"], 1) == 395.5


def test_kit_frentes_gavetas_distribuicao():
    ctx = ModuloMaterialContext(
        material_frentes="MDF Grafite 18mm",
    )
    # Gaveteiro de 500mm x 700mm, 4 gavetas
    gavetas = FrentesKitBuilder.build_kit_frentes_gavetas(
        largura_total_m=0.500,
        altura_total_m=0.700,
        num_gavetas=4,
        origin=(0.0, 0.0, 0.0),
        esp_frente_m=0.018,
        ctx=ctx,
        prefixo="Gaveteiro",
    )
    assert len(gavetas) == 4
    for i, g in enumerate(gavetas, 1):
        assert f"Frente Gaveta {i}" in g.name
        assert g.ext["trazomob"]["material"] == "MDF Grafite 18mm"
