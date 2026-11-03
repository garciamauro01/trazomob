# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Motor de precificação e orçamento do TrazoMob (Onda 3).

Calcula custo direto, markup, impostos, desconto e frete a partir da cutlist
e das preferências de preço do usuário. Gera estrutura de dados pronta para
o relatório de proposta PDF/HTML.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .preferences import TrazoMobPreferencesManager, get_preferences_file_path


@dataclass
class ItemCusto:
    """Linha de custo detalhada."""
    descricao: str
    quantidade: float
    unidade: str
    preco_unitario: float
    total: float
    categoria: str  # "chapa" | "fita" | "ferragem" | "mao_de_obra" | "frete"


@dataclass
class ResumoOrcamento:
    """Resumo consolidado do orçamento."""
    custo_direto: float = 0.0
    markup_valor: float = 0.0
    subtotal_com_markup: float = 0.0
    impostos_valor: float = 0.0
    desconto_valor: float = 0.0
    frete_valor: float = 0.0
    total_final: float = 0.0
    itens: List[ItemCusto] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "custo_direto": round(self.custo_direto, 2),
            "markup_valor": round(self.markup_valor, 2),
            "subtotal_com_markup": round(self.subtotal_com_markup, 2),
            "impostos_valor": round(self.impostos_valor, 2),
            "desconto_valor": round(self.desconto_valor, 2),
            "frete_valor": round(self.frete_valor, 2),
            "total_final": round(self.total_final, 2),
            "itens": [
                {
                    "descricao": i.descricao,
                    "quantidade": round(i.quantidade, 3),
                    "unidade": i.unidade,
                    "preco_unitario": round(i.preco_unitario, 2),
                    "total": round(i.total, 2),
                    "categoria": i.categoria,
                }
                for i in self.itens
            ],
        }


def _normalizar_material(mat: str) -> str:
    """Normaliza nome do material para chave de lookup."""
    mat = mat.strip()
    # Remove sufixos comuns que não afetam o preço
    for sufixo in [" TX", " TX ", " TX  ", "TX"]:
        if mat.endswith(sufixo):
            mat = mat[:-len(sufixo)].strip()
    return mat


def _get_chapa_preco_flexivel(chapas_precos: Dict[str, float], material: str, espessura: float) -> float:
    """Busca preço de chapa com múltiplas estratégias de chave."""
    # 1. Chave exata como vem do builder: "Material Espessuramm"
    key1 = f"{material} {espessura:.0f}mm"
    if key1 in chapas_precos:
        return chapas_precos[key1]
    
    # 2. Chave normalizada (sem TX)
    mat_norm = _normalizar_material(material)
    key2 = f"{mat_norm} {espessura:.0f}mm"
    if key2 in chapas_precos:
        return chapas_precos[key2]
    
    # 3. Busca parcial por material base
    for k, v in chapas_precos.items():
        if k.startswith(material.split()[0]) and f"{espessura:.0f}mm" in k:
            return v
        if k.startswith(mat_norm.split()[0]) and f"{espessura:.0f}mm" in k:
            return v
    
    return 0.0


def _get_fita_preco_flexivel(fita_precos: Dict[str, float], espessura_fita: float) -> float:
    """Busca preço de fita com múltiplas estratégias de chave."""
    # 1. Chave com vírgula (formato brasileiro)
    key1 = f"{espessura_fita:.2f}mm".replace(".", ",")
    if key1 in fita_precos:
        return fita_precos[key1]
    
    # 2. Chave com ponto
    key2 = f"{espessura_fita:.2f}mm"
    if key2 in fita_precos:
        return fita_precos[key2]
    
    # 3. Busca por prefixo
    for k, v in fita_precos.items():
        if k.startswith(f"{espessura_fita:.0f}"):
            return v
    
    return 0.0


def _inferir_ferragens_peca(part: Dict[str, Any]) -> Dict[str, int]:
    """Infere quantidade de ferragens necessárias baseado na peça."""
    nome_l = str(part.get("nome", "")).lower()
    qtd = part.get("quantidade", 1)

    ferragens = {
        "puxador_perfil": 0,
        "puxador_ponto": 0,
        "puxador_embutido": 0,
        "dobradica_35mm": 0,
        "corredica_telescopica_40": 0,
        "corredica_telescopica_50": 0,
        "minifix_cavilha_kit": 0,
        "parafuso_confirmat": 0,
        "pes_nivelador": 0,
    }

    # Heurística baseada no nome da peça
    if "porta" in nome_l:
        ferragens["dobradica_35mm"] += 2 * qtd  # 2 dobradiças por porta
        ferragens["puxador_perfil"] += qtd
    elif "frente de gaveta" in nome_l or "gaveta" in nome_l:
        ferragens["corredica_telescopica_40"] += qtd
        ferragens["puxador_ponto"] += qtd
    elif "prateleira" in nome_l:
        ferragens["minifix_cavilha_kit"] += 4 * qtd  # 4 suportes por prateleira
    elif "lateral" in nome_l or "base" in nome_l or "tampo" in nome_l or "travessa" in nome_l:
        ferragens["minifix_cavilha_kit"] += 4 * qtd
        ferragens["parafuso_confirmat"] += 8 * qtd
    elif "pes" in nome_l or "pé" in nome_l or "rodape" in nome_l:
        ferragens["pes_nivelador"] += qtd

    return ferragens


def _calcular_fita_metros(part: Dict[str, Any]) -> float:
    """Calcula metros lineares de fita de borda para uma peça."""
    qtd = part.get("quantidade", 1)
    comp_m = part.get("comprimento", 0.0) / 1000.0
    larg_m = part.get("largura", 0.0) / 1000.0

    metros = 0.0
    if part.get("fita_c1"):
        metros += comp_m
    if part.get("fita_c2"):
        metros += comp_m
    if part.get("fita_l1"):
        metros += larg_m
    if part.get("fita_l2"):
        metros += larg_m

    return metros * qtd


def calcular_orcamento_cutlist(parts: List[Dict[str, Any]]) -> ResumoOrcamento:
    """
    Calcula orçamento completo a partir da cutlist (lista de peças).

    Usa as preferências de preço do usuário (chapas, fitas, ferragens, mão de obra,
    markup, impostos, desconto, frete).
    """
    prefs = TrazoMobPreferencesManager.get_instance()
    pricing = prefs.get_pricing_config()

    # Parâmetros globais
    markup = pricing.get("markup", 1.35)
    impostos_pct = pricing.get("impostos_percent", 0.18)
    desconto_pct = pricing.get("desconto_percent", 0.05)
    frete_tipo = pricing.get("frete_tipo", "fixo")
    frete_valor = pricing.get("frete_valor", 150.00)
    mao_obra_m2 = pricing.get("mao_de_obra_m2", 45.00)

    chapas_precos = pricing.get("chapas_m2", {})
    fita_precos = pricing.get("fita_borda_m", {})
    ferragens_precos = pricing.get("ferragens", {})

    # Agregadores (consolidados por material/espessura para a proposta ficar limpa)
    chapa_area: Dict[str, Dict[str, float]] = {}  # descrição -> {area, preco}
    fita_metros: Dict[float, Dict[str, float]] = {}  # espessura -> {metros, preco}
    custo_chapas = 0.0
    custo_fitas = 0.0
    custo_ferragens = 0.0
    total_area_m2 = 0.0
    total_fita_m = 0.0
    ferragens_count: Dict[str, int] = {}

    # 1. Processa cada peça da cutlist
    for part in parts:
        qtd = part.get("quantidade", 1)
        mat_raw = part.get("material", "MDF Branco TX")
        esp = part.get("espessura", 15.0)
        comp_m = part.get("comprimento", 0.0) / 1000.0
        larg_m = part.get("largura", 0.0) / 1000.0
        area_m2 = comp_m * larg_m * qtd
        total_area_m2 += area_m2

        # --- Chapas (acumula por material) ---
        preco_chapa_m2 = _get_chapa_preco_flexivel(chapas_precos, mat_raw, esp)
        if preco_chapa_m2 > 0:
            # Evita "MDF Branco TX 15mm 15mm" quando o nome já traz a espessura
            if str(esp).rstrip("0").rstrip(".") + "mm" in mat_raw or f"{esp:.0f}mm" in mat_raw:
                desc = mat_raw
            else:
                desc = f"{mat_raw} {esp:.0f}mm"
            entry = chapa_area.setdefault(desc, {"area": 0.0, "preco": preco_chapa_m2})
            entry["area"] += area_m2
            custo_chapas += area_m2 * preco_chapa_m2

        # --- Fitas de borda (acumula por espessura) ---
        fita_m = _calcular_fita_metros(part)
        total_fita_m += fita_m
        esp_fita = float(part.get("espessura_fita", 0.45))
        preco_fita_m = _get_fita_preco_flexivel(fita_precos, esp_fita)
        if preco_fita_m > 0 and fita_m > 0:
            entry_f = fita_metros.setdefault(esp_fita, {"metros": 0.0, "preco": preco_fita_m})
            entry_f["metros"] += fita_m
            custo_fitas += fita_m * preco_fita_m

        # --- Ferragens inferidas ---
        ferragens_peca = _inferir_ferragens_peca(part)
        for f_key, f_qtd in ferragens_peca.items():
            if f_qtd > 0:
                ferragens_count[f_key] = ferragens_count.get(f_key, 0) + f_qtd

    # 2. Consolida chapas e fitas nos itens
    itens: List[ItemCusto] = []
    for desc, data in chapa_area.items():
        itens.append(ItemCusto(
            descricao=f"Chapa {desc}",
            quantidade=round(data["area"], 3),
            unidade="m²",
            preco_unitario=data["preco"],
            total=round(data["area"] * data["preco"], 2),
            categoria="chapa",
        ))
    for esp_fita, data in sorted(fita_metros.items()):
        itens.append(ItemCusto(
            descricao=f"Fita de borda {esp_fita:.2f}mm".replace(".", ","),
            quantidade=round(data["metros"], 2),
            unidade="m",
            preco_unitario=data["preco"],
            total=round(data["metros"] * data["preco"], 2),
            categoria="fita",
        ))

    # 3. Adiciona ferragens consolidadas
    for f_key, f_qtd in ferragens_count.items():
        preco_unit = ferragens_precos.get(f_key, 0.0)
        if preco_unit > 0:
            custo_f = f_qtd * preco_unit
            custo_ferragens += custo_f
            nome_amigavel = f_key.replace("_", " ").title()
            itens.append(ItemCusto(
                descricao=f"Ferragem: {nome_amigavel}",
                quantidade=float(f_qtd),
                unidade="un",
                preco_unitario=preco_unit,
                total=round(custo_f, 2),
                categoria="ferragem",
            ))

    # 3. Mão de obra (baseada em área total de chapa)
    custo_mao_obra = total_area_m2 * mao_obra_m2
    if custo_mao_obra > 0:
        itens.append(ItemCusto(
            descricao="Mão de obra (corte, usinagem, montagem)",
            quantidade=round(total_area_m2, 2),
            unidade="m²",
            preco_unitario=mao_obra_m2,
            total=round(custo_mao_obra, 2),
            categoria="mao_de_obra",
        ))

    # 4. Frete
    if frete_tipo == "por_m2":
        frete_calculado = total_area_m2 * frete_valor
    else:
        frete_calculado = frete_valor

    # 5. Cálculo final
    custo_direto = custo_chapas + custo_fitas + custo_ferragens + custo_mao_obra
    markup_valor = custo_direto * (markup - 1.0)
    subtotal_com_markup = custo_direto + markup_valor
    impostos_valor = subtotal_com_markup * impostos_pct
    subtotal_com_impostos = subtotal_com_markup + impostos_valor
    desconto_valor = subtotal_com_impostos * desconto_pct
    total_com_desconto = subtotal_com_impostos - desconto_valor
    total_final = total_com_desconto + frete_calculado

    # Adiciona frete aos itens se > 0
    if frete_calculado > 0:
        itens.append(ItemCusto(
            descricao="Frete / Entrega",
            quantidade=1.0,
            unidade="un",
            preco_unitario=round(frete_calculado, 2),
            total=round(frete_calculado, 2),
            categoria="frete",
        ))

    return ResumoOrcamento(
        custo_direto=round(custo_direto, 2),
        markup_valor=round(markup_valor, 2),
        subtotal_com_markup=round(subtotal_com_markup, 2),
        impostos_valor=round(impostos_valor, 2),
        desconto_valor=round(desconto_valor, 2),
        frete_valor=round(frete_calculado, 2),
        total_final=round(total_final, 2),
        itens=itens,
    )


def calcular_orcamento_por_ambiente(parts: List[Dict[str, Any]]) -> Dict[str, ResumoOrcamento]:
    """
    Calcula orçamento separado por ambiente/pavimento.
    Retorna dict { "Ambiente (Pavimento)": ResumoOrcamento }.
    """
    from collections import defaultdict

    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in parts:
        amb = p.get("ambiente") or "Ambiente Geral"
        pav = p.get("pavimento") or "Térreo"
        key = f"{amb} ({pav})" if pav else amb
        groups[key].append(p)

    result = {}
    for amb_key, amb_parts in groups.items():
        result[amb_key] = calcular_orcamento_cutlist(amb_parts)
    return result


def formatar_moeda(valor: float) -> str:
    """Formata valor como moeda brasileira."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_proposta_dados(
    parts: List[Dict[str, Any]],
    project_name: str = "Projeto TrazoMob",
    client_name: str = "Cliente",
    client_data: Optional[Dict[str, str]] = None,
    observacoes: str = "",
) -> Dict[str, Any]:
    """
    Gera estrutura completa de dados para proposta (PDF/HTML).
    Inclui orçamento geral, por ambiente, dados da empresa e cliente.
    """
    prefs = TrazoMobPreferencesManager.get_instance()
    empresa = prefs.get_empresa_config()

    orcamento_geral = calcular_orcamento_cutlist(parts)
    orcamento_por_amb = calcular_orcamento_por_ambiente(parts)

    # Estatísticas gerais
    total_pecas = sum(p.get("quantidade", 1) for p in parts)
    total_area_m2 = sum(
        (p.get("comprimento", 0) / 1000.0) * (p.get("largura", 0) / 1000.0) * p.get("quantidade", 1)
        for p in parts
    )
    total_fita_m = sum(_calcular_fita_metros(p) for p in parts)

    from datetime import datetime
    data_emissao = datetime.now().strftime("%d/%m/%Y")
    validade = 30  # dias

    return {
        "projeto": project_name,
        "cliente": client_name,
        "cliente_dados": client_data or {},
        "data_emissao": data_emissao,
        "validade_dias": validade,
        "observacoes": observacoes,
        "empresa": empresa,
        "estatisticas": {
            "total_pecas": total_pecas,
            "total_area_m2": round(total_area_m2, 2),
            "total_fita_m": round(total_fita_m, 1),
            "num_ambientes": len(orcamento_por_amb),
        },
        "orcamento_geral": orcamento_geral.to_dict(),
        "orcamento_por_ambiente": {
            k: v.to_dict() for k, v in orcamento_por_amb.items()
        },
        "itens_detalhados": orcamento_geral.itens,  # para compatibilidade
    }