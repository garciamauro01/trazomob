# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Regressão do Balcão Porta-Tempero.

O registro de módulos repassa os parâmetros de fundo (``tipo_fundo``,
``esp_fundo_mm`` etc.) para todos os construtores de caixa inferior. O
``build_porta_tempero`` não aceitava esses argumentos e a inserção pela
galeria falhava com ``TypeError: unexpected keyword argument 'tipo_fundo'``.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from plugins.trazomob.builders.cabinet import CabinetBuilder
from plugins.trazomob.domain.catalog import MODULE_CATALOG
from plugins.trazomob.domain.module_geometry import build_default_module_params


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _porta_tempero_params(tipo_fundo: str) -> dict:
    cat = next(
        m for c in MODULE_CATALOG.values() for m in c
        if m.get("id") == "porta_tempero")
    params = build_default_module_params(cat)
    params["tipo_fundo"] = tipo_fundo
    return params


@pytest.mark.parametrize("tipo_fundo", ["rasgo", "sem_fundo"])
def test_insercao_pela_galeria_aceita_parametros_de_fundo(qapp, tipo_fundo):
    mod = CabinetBuilder.build_module_group(
        _porta_tempero_params(tipo_fundo), offset=(0.0, 0.0, 0.0))

    nomes = [c.name for c in mod.children]
    assert any("Frente" in n for n in nomes)
    tem_fundo = any("Fundo" in n for n in nomes)
    assert tem_fundo is (tipo_fundo != "sem_fundo")
