# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Testes automatizados para o sistema de internacionalização (i18n) do TrazoMob."""
from __future__ import annotations

import json
import os

from plugins.trazomob.domain.i18n import clear_i18n_cache, get_lang, tr
from plugins.trazomob.domain.catalog import MODULE_CATALOG


def test_i18n_json_files_valid():
    """Garante que es.json e en.json existem, são JSON válidos e possuem as mesmas chaves."""
    base_dir = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "i18n")
    )
    es_path = os.path.join(base_dir, "es.json")
    en_path = os.path.join(base_dir, "en.json")

    assert os.path.isfile(es_path), "Arquivo es.json não encontrado"
    assert os.path.isfile(en_path), "Arquivo en.json não encontrado"

    with open(es_path, "r", encoding="utf-8") as f:
        es_data = json.load(f)
    with open(en_path, "r", encoding="utf-8") as f:
        en_data = json.load(f)

    assert len(es_data) >= 200
    assert len(en_data) >= 200
    assert set(es_data.keys()) == set(en_data.keys()), "Chaves divergentes entre es.json e en.json"


def test_tr_translations_pt_es_en(monkeypatch):
    """Valida a tradução dinâmica entre Português (pt-BR), Espanhol (es) e Inglês (en)."""
    import core.i18n as core_i18n

    # 1. Português (nativo / fallback direto)
    monkeypatch.setattr(core_i18n, "current_language", lambda: "pt-BR")
    clear_i18n_cache()
    assert get_lang() == "pt-BR"
    assert tr("Medidas") == "Medidas"
    assert tr("Largura:") == "Largura:"
    assert tr("Balcão de Canto Reto (L Cego)") == "Balcão de Canto Reto (L Cego)"

    # 2. Espanhol (es)
    monkeypatch.setattr(core_i18n, "current_language", lambda: "es")
    clear_i18n_cache()
    assert get_lang() == "es"
    assert tr("Largura:") == "Ancho:"
    assert tr("Altura:") == "Altura:"
    assert tr("Profundidade:") == "Profundidad:"
    assert tr("Balcão de Canto Reto (L Cego)") == "Módulo Bajo Rincón Recto (Ciego)"
    assert tr("Régua Fechamento:") == "Regleta de Cierre:"

    # 3. Inglês (en)
    monkeypatch.setattr(core_i18n, "current_language", lambda: "en")
    clear_i18n_cache()
    assert get_lang() == "en"
    assert tr("Medidas") == "Dimensions"
    assert tr("Largura:") == "Width:"
    assert tr("Altura:") == "Height:"
    assert tr("Profundidade:") == "Depth:"
    assert tr("Balcão de Canto Reto (L Cego)") == "Blind Corner Base Cabinet"
    assert tr("Régua Fechamento:") == "Filler Strip:"

    # 4. Fallback seguro para chaves não cadastradas e interpolação kwargs
    assert tr("Texto Inexistente {n}", n=42) == "Texto Inexistente 42"


def test_catalog_categories_and_modules_translated(monkeypatch):
    """Verifica que todas as categorias principais do MODULE_CATALOG possuem tradução em es e en."""
    import core.i18n as core_i18n

    for lang in ("es", "en"):
        monkeypatch.setattr(core_i18n, "current_language", lambda: lang)
        clear_i18n_cache()
        for cat_name, items in MODULE_CATALOG.items():
            # Categoria traduzida não deve ser vazia
            translated_cat = tr(cat_name)
            assert isinstance(translated_cat, str) and len(translated_cat) > 0
            for item in items:
                nome = item.get("nome", "")
                if nome:
                    assert len(tr(nome)) > 0
