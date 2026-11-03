# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Testes do motor de precificação e da proposta comercial (Onda 3)."""

from __future__ import annotations

import copy

import pytest

from plugins.trazomob.preferences import DEFAULT_PREFERENCES, TrazoMobPreferencesManager
from plugins.trazomob.pricing import (
    _get_chapa_preco_flexivel,
    _get_fita_preco_flexivel,
    calcular_orcamento_cutlist,
    calcular_orcamento_por_ambiente,
    formatar_moeda,
    gerar_proposta_dados,
)


@pytest.fixture()
def prefs():
    """Instancia o manager com a seção de preços restaurada para os padrões."""
    manager = TrazoMobPreferencesManager.get_instance()
    original = copy.deepcopy(manager._data.get("pricing", {}))
    manager._data["pricing"] = copy.deepcopy(DEFAULT_PREFERENCES["pricing"])
    try:
        yield manager
    finally:
        manager._data["pricing"] = original


def _peca(nome="Lateral Esquerda", comp=800, larg=550, esp=15, qtd=1,
          material="MDF Branco TX 15mm", fitas=(True, False, True, False),
          esp_fita=0.45, ambiente=None, pavimento=None):
    part = {
        "nome": nome,
        "comprimento": comp,
        "largura": larg,
        "espessura": esp,
        "quantidade": qtd,
        "material": material,
        "fita_c1": fitas[0],
        "fita_c2": fitas[1],
        "fita_l1": fitas[2],
        "fita_l2": fitas[3],
        "espessura_fita": esp_fita,
    }
    if ambiente is not None:
        part["ambiente"] = ambiente
    if pavimento is not None:
        part["pavimento"] = pavimento
    return part


# ─────────────────────────────────────────────────────────────────────────────
# Formatação e lookups flexíveis
# ─────────────────────────────────────────────────────────────────────────────

def test_formatar_moeda():
    assert formatar_moeda(0) == "R$ 0,00"
    assert formatar_moeda(1234.5) == "R$ 1.234,50"
    assert formatar_moeda(0.999) == "R$ 1,00"


def test_chapa_lookup_exato_e_sem_tx():
    tabela = {"MDF Branco TX 15mm": 85.0, "MDF Branco 15mm": 80.0}
    assert _get_chapa_preco_flexivel(tabela, "MDF Branco TX", 15) == 85.0
    assert _get_chapa_preco_flexivel(tabela, "MDF Branco", 15) == 80.0


def test_chapa_lookup_por_prefixo_e_desconhecido():
    tabela = {"MDF Branco TX 15mm": 85.0}
    # Nome do builder já com espessura inclusa
    assert _get_chapa_preco_flexivel(tabela, "MDF Branco TX 15mm", 15) == 85.0
    assert _get_chapa_preco_flexivel(tabela, "Compensado Naval", 15) == 0.0


def test_fita_lookup_virgula_ponto_e_prefixo():
    tabela = {"0,45mm": 1.80, "1.0mm": 2.50}
    assert _get_fita_preco_flexivel(tabela, 0.45) == 1.80
    assert _get_fita_preco_flexivel(tabela, 1.0) == 2.50
    assert _get_fita_preco_flexivel({"0,45mm": 1.80}, 0.45) == 1.80
    assert _get_fita_preco_flexivel({}, 0.45) == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Cálculo do orçamento
# ─────────────────────────────────────────────────────────────────────────────

def test_orcamento_basico_matematica(prefs):
    parts = [_peca(comp=1000, larg=1000, qtd=2)]  # 2 m²
    orc = calcular_orcamento_cutlist(parts)

    assert orc.custo_direto > 0
    assert orc.markup_valor == pytest.approx(orc.custo_direto * 0.35, abs=0.02)
    assert orc.subtotal_com_markup == pytest.approx(orc.custo_direto * 1.35, abs=0.02)
    assert orc.impostos_valor == pytest.approx(orc.subtotal_com_markup * 0.18, abs=0.02)
    esperado = (
        (orc.custo_direto * 1.35)
        + (orc.custo_direto * 1.35 * 0.18)
    )
    esperado -= esperado * 0.05
    esperado += 150.0
    assert orc.total_final == pytest.approx(esperado, abs=0.05)


def test_orcamento_tem_chapa_e_fita(prefs):
    orc = calcular_orcamento_cutlist([_peca()])
    categorias = {i.categoria for i in orc.itens}
    assert "chapa" in categorias
    assert "fita" in categorias
    assert "ferragem" in categorias
    assert "mao_de_obra" in categorias
    assert "frete" in categorias

    chapas = [i for i in orc.itens if i.categoria == "chapa"]
    fitas = [i for i in orc.itens if i.categoria == "fita"]
    # Consolidado: uma linha por material / espessura de fita
    assert len(chapas) == 1
    assert len(fitas) == 1
    assert fitas[0].quantidade == pytest.approx(1.35, abs=0.01)  # 0.8 + 0.55


def test_orcamento_consolida_repetidas(prefs):
    parts = [_peca(qtd=3), _peca(qtd=2)]
    orc = calcular_orcamento_cutlist(parts)
    chapas = [i for i in orc.itens if i.categoria == "chapa"]
    assert len(chapas) == 1
    # 5 peças de 0.8 x 0.55 = 2.2 m²
    assert chapas[0].quantidade == pytest.approx(2.2, abs=0.001)


def test_orcamento_sem_preco_de_chapa(prefs):
    orc = calcular_orcamento_cutlist([_peca(material="Material Inexistente 15mm")])
    chapas = [i for i in orc.itens if i.categoria == "chapa"]
    assert chapas == []
    # Mão de obra e frete continuam sendo cobrados
    assert orc.custo_direto > 0


def test_frete_por_m2(prefs):
    prefs._data["pricing"]["frete_tipo"] = "por_m2"
    prefs._data["pricing"]["frete_valor"] = 10.0
    orc = calcular_orcamento_cutlist([_peca(comp=1000, larg=1000)])  # 1 m²
    assert orc.frete_valor == pytest.approx(10.0, abs=0.01)


def test_orcamento_por_ambiente(prefs):
    parts = [
        _peca(ambiente="Cozinha", pavimento="Térreo"),
        _peca(ambiente="Quarto", pavimento="Superior"),
        _peca(ambiente="Cozinha", pavimento="Térreo"),
    ]
    por_amb = calcular_orcamento_por_ambiente(parts)
    assert "Cozinha (Térreo)" in por_amb
    assert "Quarto (Superior)" in por_amb
    assert por_amb["Cozinha (Térreo)"].total_final > 0
    # A soma dos custos diretos por ambiente bate com o cálculo global
    total_amb = sum(o.custo_direto for o in por_amb.values())
    total_geral = calcular_orcamento_cutlist(parts).custo_direto
    assert total_amb == pytest.approx(total_geral, abs=0.05)


def test_proposta_dados_estrutura(prefs):
    dados = gerar_proposta_dados(
        parts=[_peca()],
        project_name="Cozinha",
        client_name="Maria",
        client_data={"telefone": "123"},
    )
    assert dados["cliente"] == "Maria"
    assert dados["projeto"] == "Cozinha"
    assert "orcamento_geral" in dados
    assert "orcamento_por_ambiente" in dados
    assert dados["estatisticas"]["total_pecas"] == 1
    assert dados["empresa"]["nome"]


# ─────────────────────────────────────────────────────────────────────────────
# Documentos HTML
# ─────────────────────────────────────────────────────────────────────────────

def test_proposta_html_contem_cliente_e_total(prefs, tmp_path):
    from plugins.trazomob.production_report import generate_proposal_html

    destino = tmp_path / "proposta.html"
    html = generate_proposal_html(
        parts=[_peca()],
        project_name="Cozinha Gourmet",
        client_name="Maria Souza",
        client_data={"telefone": "(11) 98888-7777", "cpf_cnpj": "000.000.000-00"},
        observacoes="Entrega em 30 dias.",
        filepath=destino,
    )
    assert destino.exists()
    assert "Maria Souza" in html
    assert "Cozinha Gourmet" in html
    assert "Proposta Comercial" in html
    assert "000.000.000-00" in html
    assert "Entrega em 30 dias." in html
    assert formatar_moeda(calcular_orcamento_cutlist([_peca()]).total_final) in html
    assert "Imprimir / Salvar PDF" in html


def test_relatorio_com_e_sem_orcamento(prefs):
    from plugins.trazomob.production_report import generate_project_html_report

    parts = [_peca()]
    sem = generate_project_html_report(parts, project_name="Projeto X")
    assert "Orçamento Detalhado" not in sem
    assert "Lista Completa de Peças" in sem

    com = generate_project_html_report(parts, project_name="Projeto X", include_pricing=True)
    assert "Orçamento Detalhado" in com
    assert "Resumo Financeiro" in com
    assert formatar_moeda(calcular_orcamento_cutlist(parts).total_final) in com
