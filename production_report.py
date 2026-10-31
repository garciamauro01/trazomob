# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Gerador de Relatório Executivo e Orçamento Técnico em HTML / Impressão (TrazoMob).

Produz um documento completo e formatado contendo:
- Dados gerais do projeto e cliente
- Resumo executivo de chapas e m²
- Metragem linear estimada de fitas de borda por espessura
- Relação de ferragens (dobradiças, corrediças, puxadores, parafusos/minifix)
- Lista detalhada de peças com medidas de corte bruto e final
"""
from __future__ import annotations

import math
from typing import Any, List, Dict
from pathlib import Path

def generate_project_html_report(
    parts: List[dict[str, Any]],
    project_name: str = "Projeto TrazoMob",
    client_name: str = "Cliente",
) -> str:
    """Gera um relatório executivo completo em HTML com design limpo e profissional."""
    total_pecas = sum(p.get("quantidade", 1) for p in parts)

    # Agrupa por material
    by_mat: Dict[str, Dict[str, float]] = {}
    total_area_m2 = 0.0
    total_linear_tape_m = 0.0

    # Estimativa de ferragens
    total_puxadores = 0
    total_dobradicas = 0
    total_corredicas = 0

    for p in parts:
        qtd = p.get("quantidade", 1)
        mat = str(p.get("material", "MDF"))
        comp_m = float(p.get("comprimento", 0.0)) / 1000.0
        larg_m = float(p.get("largura", 0.0)) / 1000.0
        area_m2 = comp_m * larg_m * qtd
        total_area_m2 += area_m2

        if mat not in by_mat:
            by_mat[mat] = {"area": 0.0, "pecas": 0}
        by_mat[mat]["area"] += area_m2
        by_mat[mat]["pecas"] += qtd

        # Fitas de borda
        tape_len = 0.0
        if p.get("fita_c1"):
            tape_len += comp_m
        if p.get("fita_c2"):
            tape_len += comp_m
        if p.get("fita_l1"):
            tape_len += larg_m
        if p.get("fita_l2"):
            tape_len += larg_m
        total_linear_tape_m += tape_len * qtd

        # Ferragens
        nome_l = str(p.get("nome", "")).lower()
        if "porta" in nome_l:
            total_puxadores += qtd
            total_dobradicas += 2 * qtd
        elif "frente de gaveta" in nome_l:
            total_puxadores += qtd
            total_corredicas += qtd

    # Tabela de materiais
    mat_rows = ""
    for mat, data in by_mat.items():
        area = data["area"]
        chapas_est = math.ceil(area / (2.75 * 1.85 * 0.85))  # 85% aproveitamento
        mat_rows += f"""
        <tr>
            <td><b>{mat}</b></td>
            <td style="text-align: center;">{data['pecas']}</td>
            <td style="text-align: right;">{area:.2f} m²</td>
            <td style="text-align: right;"><b>~{chapas_est} chapa(s)</b></td>
        </tr>
        """

    # Tabela detalhada de peças
    part_rows = ""
    for i, p in enumerate(parts):
        qtd = p.get("quantidade", 1)
        comp = f"{p.get('comprimento', 0.0):.0f}"
        larg = f"{p.get('largura', 0.0):.0f}"
        comp_c = f"{p.get('comprimento_corte', p.get('comprimento', 0.0)):.0f}"
        larg_c = f"{p.get('largura_corte', p.get('largura', 0.0)):.0f}"
        esp = f"{p.get('espessura', 15.0):.0f}"
        fitas = f"C:{int(bool(p.get('fita_c1')))}/{int(bool(p.get('fita_c2')))} L:{int(bool(p.get('fita_l1')))}/{int(bool(p.get('fita_l2')))}"
        part_rows += f"""
        <tr>
            <td style="text-align: center;">{i+1}</td>
            <td><b>{p.get('nome', 'Peça')}</b></td>
            <td style="text-align: center;"><b>{qtd}</b></td>
            <td style="text-align: right;">{comp} x {larg} x {esp}</td>
            <td style="text-align: right; color: #475569;">{comp_c} x {larg_c}</td>
            <td>{p.get('material', '')}</td>
            <td style="text-align: center; font-size: 11px;">{fitas}</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Relatório Executivo — {project_name}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 30px; color: #1E293B; background: #FFF; }}
    h1 {{ color: #0F172A; margin-bottom: 4px; font-size: 24px; }}
    .subtitle {{ color: #64748B; font-size: 13px; margin-bottom: 24px; }}
    .cards-row {{ display: flex; gap: 16px; margin-bottom: 24px; }}
    .card {{ flex: 1; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px; }}
    .card-title {{ font-size: 11px; font-weight: bold; color: #64748B; text-transform: uppercase; margin-bottom: 6px; }}
    .card-val {{ font-size: 20px; font-weight: bold; color: #0284C7; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; font-size: 12px; }}
    th {{ background: #F1F5F9; color: #334155; font-weight: bold; text-align: left; padding: 8px 10px; border-bottom: 2px solid #CBD5E1; }}
    td {{ padding: 7px 10px; border-bottom: 1px solid #E2E8F0; }}
    tr:nth-child(even) {{ background: #F8FAFC; }}
    .section-title {{ font-size: 15px; font-weight: bold; color: #0F172A; margin: 20px 0 8px 0; border-left: 4px solid #0284C7; padding-left: 8px; }}
    .footer {{ font-size: 11px; color: #94A3B8; text-align: center; margin-top: 40px; border-top: 1px solid #E2E8F0; padding-top: 12px; }}
</style>
</head>
<body>
    <h1>📄 Relatório Executivo & Orçamento Técnico</h1>
    <div class="subtitle">Projeto: <b>{project_name}</b> | Cliente: <b>{client_name}</b> | Sistema IngeTrazo / TrazoMob</div>

    <div class="cards-row">
        <div class="card">
            <div class="card-title">Total de Peças</div>
            <div class="card-val">{total_pecas} un.</div>
        </div>
        <div class="card">
            <div class="card-title">Área Total de Chapa</div>
            <div class="card-val">{total_area_m2:.2f} m²</div>
        </div>
        <div class="card">
            <div class="card-title">Fita de Borda</div>
            <div class="card-val">~{int(round(total_linear_tape_m))} metros</div>
        </div>
        <div class="card">
            <div class="card-title">Puxadores / Ferragens</div>
            <div class="card-val">{total_puxadores} pux. | {total_dobradicas} dobr.</div>
        </div>
    </div>

    <div class="section-title">📊 Resumo de Chapas & Consumo de Materiais</div>
    <table>
        <thead>
            <tr>
                <th>Padrão / Material</th>
                <th style="text-align: center;">Qtd Peças</th>
                <th style="text-align: right;">Área Total</th>
                <th style="text-align: right;">Estimativa de Chapas (2750x1850)</th>
            </tr>
        </thead>
        <tbody>
            {mat_rows}
        </tbody>
    </table>

    <div class="section-title">📋 Lista Completa de Peças para Fabricação</div>
    <table>
        <thead>
            <tr>
                <th style="text-align: center;">#</th>
                <th>Descrição / Peça</th>
                <th style="text-align: center;">Qtd</th>
                <th style="text-align: right;">Medida Final (mm)</th>
                <th style="text-align: right;">Corte Bruto (mm)</th>
                <th>Material</th>
                <th style="text-align: center;">Fitas (C/L)</th>
            </tr>
        </thead>
        <tbody>
            {part_rows}
        </tbody>
    </table>

    <div class="footer">
        Documento gerado automaticamente pelo TrazoMob — Solução Paramétrica para Design de Interiores e Marcenaria.
    </div>
</body>
</html>
"""
    return html

