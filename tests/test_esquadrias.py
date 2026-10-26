# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Testes unitários para o construtor de esquadrias (portas e janelas paramétricas)."""
import pytest
from plugins.trazomob.builder_esquadrias import EsquadriaBuilder


def test_build_porta_giro():
    """Testa geração de porta de giro com marco, alisar e folha."""
    porta = EsquadriaBuilder.build_porta_giro(
        largura_mm=800.0,
        altura_mm=2100.0,
        esp_parede_mm=150.0,
        lado_abertura="right",
        acabamento="madeira_branca",
    )

    assert "Porta Giro 800x2100" in porta.name
    assert "trazomob_esquadria" in porta.ext
    info = porta.ext["trazomob_esquadria"]
    assert info["tipo"] == "porta_giro"
    assert info["largura_mm"] == 800.0
    assert info["altura_mm"] == 2100.0

    children = getattr(porta, "children", []) or getattr(porta, "groups", [])
    # Deve conter batentes, alisares frontais/traseiros, folha e maçaneta
    assert len(children) >= 10

    # Verifica se a folha da porta foi criada
    folhas = [c for c in children if "Folha da Porta" in c.name]
    assert len(folhas) == 1


def test_build_janela_correr():
    """Testa geração de janela de correr de 2 folhas com caixilho e vidro."""
    janela = EsquadriaBuilder.build_janela_correr(
        largura_mm=1200.0,
        altura_mm=1000.0,
        esp_parede_mm=150.0,
        peitoril_mm=1100.0,
        acabamento_aluminio="aluminio_preto",
        tipo_vidro="vidro_incolor",
    )

    assert "Janela Correr 1200x1000" in janela.name
    assert "trazomob_esquadria" in janela.ext
    info = janela.ext["trazomob_esquadria"]
    assert info["tipo"] == "janela_correr"
    assert info["peitoril_mm"] == 1100.0

    children = getattr(janela, "children", []) or getattr(janela, "groups", [])
    # Marco (4) + 2 folhas x (4 quadros + 1 vidro) = 14 peças
    assert len(children) >= 14

    vidros = [c for c in children if "Vidro" in c.name]
    assert len(vidros) == 2


def test_build_janela_maximar():
    """Testa janela Maxim-Ar para banheiros."""
    maximar = EsquadriaBuilder.build_janela_maximar(
        largura_mm=600.0,
        altura_mm=600.0,
        peitoril_mm=1600.0,
    )

    assert "Maxim-Ar 600x600" in maximar.name
    info = maximar.ext["trazomob_esquadria"]
    assert info["tipo"] == "janela_maximar"
    assert info["peitoril_mm"] == 1600.0
