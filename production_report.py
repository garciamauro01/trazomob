# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Gerador de Relatório Executivo, Orçamento Técnico e Proposta Comercial (TrazoMob Onda 3).

Produz documentos em HTML prontos para impressão/PDF:
- Relatório de produção (materiais, peças, fitas, ferragens)
- Orçamento detalhado com preços, markup, impostos, desconto, frete
- Proposta comercial com dados do cliente, empresa, validade
"""
from __future__ import annotations

import math
from typing import Any, List, Dict, Optional
from pathlib import Path

from .pricing import (
    calcular_orcamento_cutlist,
    calcular_orcamento_por_ambiente,
    gerar_proposta_dados,
    formatar_moeda,
)


def generate_project_html_report(
    parts: List[dict[str, Any]],
    project_name: str = "Projeto TrazoMob",
    client_name: str = "Cliente",
    include_pricing: bool = False,
    client_data: Optional[Dict[str, str]] = None,
) -> str:
    """Gera um relatório executivo completo em HTML com design limpo e profissional.
    
    Args:
        parts: Lista de peças da cutlist
        project_name: Nome do projeto
        client_name: Nome do cliente
        include_pricing: Se True, inclui seção de orçamento/preços
        client_data: Dados adicionais do cliente (endereço, telefone, etc.)
    """
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

    # Seção de orçamento (opcional)
    orcamento_html = ""
    if include_pricing:
        from .preferences import TrazoMobPreferencesManager
        prefs = TrazoMobPreferencesManager.get_instance()
        empresa = prefs.get_empresa_config()
        
        orcamento = calcular_orcamento_cutlist(parts)
        orcamento_por_amb = calcular_orcamento_por_ambiente(parts)
        
        # Tabela de custos diretos
        custo_rows = ""
        for item in orcamento.itens:
            custo_rows += f"""
            <tr>
                <td>{item.descricao}</td>
                <td style="text-align: center;">{item.quantidade:.3f}</td>
                <td style="text-align: center;">{item.unidade}</td>
                <td style="text-align: right;">{formatar_moeda(item.preco_unitario)}</td>
                <td style="text-align: right;"><b>{formatar_moeda(item.total)}</b></td>
                <td style="text-align: center; text-transform: capitalize;">{item.categoria}</td>
            </tr>
            """
        
        # Resumo financeiro
        orcamento_html = f"""
        <div class="section-title">💰 Orçamento Detalhado</div>
        <table>
            <thead>
                <tr>
                    <th>Item</th>
                    <th style="text-align: center;">Qtd</th>
                    <th style="text-align: center;">Un</th>
                    <th style="text-align: right;">Preço Unit.</th>
                    <th style="text-align: right;">Total</th>
                    <th style="text-align: center;">Categoria</th>
                </tr>
            </thead>
            <tbody>
                {custo_rows}
            </tbody>
        </table>
        
        <div class="section-title">📊 Resumo Financeiro</div>
        <table style="max-width: 500px;">
            <tr><td>Custo Direto (materiais + mão de obra)</td><td style="text-align: right;"><b>{formatar_moeda(orcamento.custo_direto)}</b></td></tr>
            <tr><td>Markup ({prefs.get_markup():.0%})</td><td style="text-align: right;">{formatar_moeda(orcamento.markup_valor)}</td></tr>
            <tr><td>Subtotal com Markup</td><td style="text-align: right;"><b>{formatar_moeda(orcamento.subtotal_com_markup)}</b></td></tr>
            <tr><td>Impostos ({prefs.get_impostos_percent():.0%})</td><td style="text-align: right;">{formatar_moeda(orcamento.impostos_valor)}</td></tr>
            <tr><td>Subtotal com Impostos</td><td style="text-align: right;"><b>{formatar_moeda(orcamento.subtotal_com_markup + orcamento.impostos_valor)}</b></td></tr>
            <tr><td>Desconto ({prefs.get_desconto_percent():.0%})</td><td style="text-align: right;">-{formatar_moeda(orcamento.desconto_valor)}</td></tr>
            <tr><td>Frete</td><td style="text-align: right;">{formatar_moeda(orcamento.frete_valor)}</td></tr>
            <tr style="border-top: 2px solid #0284C7; font-size: 14px;">
                <td><b>TOTAL FINAL</b></td>
                <td style="text-align: right;"><b>{formatar_moeda(orcamento.total_final)}</b></td>
            </tr>
        </table>
        
        <div class="section-title">🏠 Orçamento por Ambiente</div>
        """
        
        for amb_key, amb_orc in orcamento_por_amb.items():
            orcamento_html += f"""
            <div style="margin-bottom: 16px; padding: 12px; background: #F8FAFC; border-radius: 6px; border-left: 4px solid #16A34A;">
                <div style="font-weight: bold; margin-bottom: 8px;">{amb_key}</div>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; font-size: 12px;">
                    <div>Custo Direto: <b>{formatar_moeda(amb_orc.custo_direto)}</b></div>
                    <div>Com Markup: <b>{formatar_moeda(amb_orc.subtotal_com_markup)}</b></div>
                    <div>Total: <b>{formatar_moeda(amb_orc.total_final)}</b></div>
                </div>
            </div>
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
    @media print {{
        body {{ margin: 0; padding: 20px; }}
        .no-print {{ display: none; }}
    }}
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

    {orcamento_html}

    <div class="footer">
        Documento gerado automaticamente pelo TrazoMob — Solução Paramétrica para Design de Interiores e Marcenaria.
    </div>
</body>
</html>
"""
    return html


def generate_proposal_html(
    parts: List[dict[str, Any]],
    project_name: str = "Projeto TrazoMob",
    client_name: str = "Cliente",
    client_data: Optional[Dict[str, str]] = None,
    observacoes: str = "",
    filepath: Optional[str | Path] = None,
) -> str:
    """Gera uma proposta comercial completa em HTML (pronta para PDF).
    
    Inclui:
    - Cabeçalho com dados da empresa e cliente
    - Descrição do projeto e ambientes
    - Orçamento detalhado com preços
    - Condições comerciais e validade
    - Assinatura
    
    Args:
        parts: Lista de peças da cutlist
        project_name: Nome do projeto
        client_name: Nome do cliente
        client_data: Dict com endereço, telefone, email, cpf_cnpj do cliente
        observacoes: Observações livres para a proposta
        filepath: Se fornecido, salva o arquivo no disco
        
    Returns:
        HTML da proposta como string
    """
    from datetime import datetime, timedelta
    from .preferences import TrazoMobPreferencesManager
    
    prefs = TrazoMobPreferencesManager.get_instance()
    empresa = prefs.get_empresa_config()
    
    proposta = gerar_proposta_dados(
        parts=parts,
        project_name=project_name,
        client_name=client_name,
        client_data=client_data,
        observacoes=observacoes,
    )
    
    orc = proposta["orcamento_geral"]
    stats = proposta["estatisticas"]
    data_emissao = proposta["data_emissao"]
    validade = proposta["validade_dias"]
    data_validade = (datetime.now() + timedelta(days=validade)).strftime("%d/%m/%Y")
    
    # Dados da empresa
    emp_nome = empresa.get("nome", "Marcenaria TrazoMob")
    emp_cnpj = empresa.get("cnpj", "")
    emp_end = empresa.get("endereco", "")
    emp_cid = empresa.get("cidade", "")
    emp_tel = empresa.get("telefone", "")
    emp_email = empresa.get("email", "")
    
    # Dados do cliente
    cli_end = client_data.get("endereco", "") if client_data else ""
    cli_cid = client_data.get("cidade", "") if client_data else ""
    cli_tel = client_data.get("telefone", "") if client_data else ""
    cli_email = client_data.get("email", "") if client_data else ""
    cli_doc = client_data.get("cpf_cnpj", "") if client_data else ""
    
    # Itens do orçamento
    item_rows = ""
    for item in orc["itens"]:
        item_rows += f"""
        <tr>
            <td>{item['descricao']}</td>
            <td style="text-align: center;">{item['quantidade']:.3f}</td>
            <td style="text-align: center;">{item['unidade']}</td>
            <td style="text-align: right;">{formatar_moeda(item['preco_unitario'])}</td>
            <td style="text-align: right;"><b>{formatar_moeda(item['total'])}</b></td>
        </tr>
        """
    
    # Orçamento por ambiente
    amb_rows = ""
    for amb_key, amb_orc in proposta["orcamento_por_ambiente"].items():
        amb_rows += f"""
        <tr>
            <td><b>{amb_key}</b></td>
            <td style="text-align: right;">{formatar_moeda(amb_orc['custo_direto'])}</td>
            <td style="text-align: right;">{formatar_moeda(amb_orc['subtotal_com_markup'])}</td>
            <td style="text-align: right;"><b>{formatar_moeda(amb_orc['total_final'])}</b></td>
        </tr>
        """
    
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Proposta Comercial — {project_name}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 40px; color: #1E293B; background: #FFF; }}
    .container {{ max-width: 900px; margin: 0 auto; }}
    .header {{ display: flex; justify-content: space-between; border-bottom: 3px solid #0284C7; padding-bottom: 20px; margin-bottom: 30px; }}
    .logo {{ font-size: 28px; font-weight: bold; color: #0284C7; }}
    .title {{ font-size: 24px; font-weight: bold; color: #0F172A; margin: 20px 0; text-align: center; }}
    .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }}
    .info-box {{ background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; }}
    .info-box h3 {{ margin: 0 0 12px 0; font-size: 13px; color: #64748B; text-transform: uppercase; border-bottom: 1px solid #E2E8F0; padding-bottom: 8px; }}
    .info-row {{ display: flex; justify-content: space-between; margin: 6px 0; font-size: 13px; }}
    .info-label {{ color: #64748B; }}
    .info-value {{ font-weight: 500; }}
    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 12px; }}
    th {{ background: #0284C7; color: white; font-weight: 600; text-align: left; padding: 10px; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid #E2E8F0; }}
    tr:nth-child(even) {{ background: #F8FAFC; }}
    .totals-table {{ max-width: 400px; margin-left: auto; font-size: 13px; }}
    .totals-table td {{ padding: 8px 12px; border: none; }}
    .totals-table tr:last-child td {{ border-top: 2px solid #0284C7; font-weight: bold; font-size: 15px; }}
    .section {{ margin: 30px 0; }}
    .section h2 {{ font-size: 16px; color: #0F172A; border-left: 4px solid #0284C7; padding-left: 12px; margin-bottom: 16px; }}
    .notes {{ background: #FEF3C7; border: 1px solid #FCD34D; border-radius: 8px; padding: 16px; margin: 20px 0; font-size: 13px; line-height: 1.6; }}
    .signature {{ display: flex; justify-content: space-between; margin-top: 60px; }}
    .sig-block {{ text-align: center; width: 45%; }}
    .sig-line {{ border-top: 1px solid #334155; margin-top: 60px; padding-top: 8px; font-size: 12px; }}
    .validade {{ text-align: right; color: #DC2626; font-weight: bold; margin: 20px 0; }}
    .print-btn {{ position: fixed; top: 20px; right: 20px; padding: 10px 20px; background: #0284C7; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; z-index: 100; }}
    @media print {{
        .print-btn {{ display: none; }}
        body {{ padding: 0; }}
        .container {{ max-width: 100%; }}
    }}
</style>
</head>
<body>
    <button class="print-btn" onclick="window.print()">🖨️ Imprimir / Salvar PDF</button>
    
    <div class="container">
        <div class="header">
            <div>
                <div class="logo">{emp_nome}</div>
                <div style="font-size: 12px; color: #64748B; margin-top: 4px;">
                    {emp_end}<br>
                    {emp_cid}<br>
                    CNPJ: {emp_cnpj} | Tel: {emp_tel} | Email: {emp_email}
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 11px; color: #64748B;">PROPOSTA COMERCIAL</div>
                <div style="font-size: 20px; font-weight: bold; color: #0F172A; margin-top: 4px;">Nº {datetime.now().strftime("%Y%m%d%H%M")}</div>
            </div>
        </div>
        
        <div class="title">Proposta para <span style="color: #0284C7;">{client_name}</span> — {project_name}</div>
        
        <div class="info-grid">
            <div class="info-box">
                <h3>Emitente</h3>
                <div class="info-row"><span class="info-label">Empresa:</span><span class="info-value">{emp_nome}</span></div>
                <div class="info-row"><span class="info-label">CNPJ:</span><span class="info-value">{emp_cnpj}</span></div>
                <div class="info-row"><span class="info-label">Endereço:</span><span class="info-value">{emp_end}</span></div>
                <div class="info-row"><span class="info-label">Cidade:</span><span class="info-value">{emp_cid}</span></div>
                <div class="info-row"><span class="info-label">Telefone:</span><span class="info-value">{emp_tel}</span></div>
                <div class="info-row"><span class="info-label">Email:</span><span class="info-value">{emp_email}</span></div>
            </div>
            <div class="info-box">
                <h3>Cliente</h3>
                <div class="info-row"><span class="info-label">Nome:</span><span class="info-value">{client_name}</span></div>
                <div class="info-row"><span class="info-label">CPF/CNPJ:</span><span class="info-value">{cli_doc}</span></div>
                <div class="info-row"><span class="info-label">Endereço:</span><span class="info-value">{cli_end}</span></div>
                <div class="info-row"><span class="info-label">Cidade:</span><span class="info-value">{cli_cid}</span></div>
                <div class="info-row"><span class="info-label">Telefone:</span><span class="info-value">{cli_tel}</span></div>
                <div class="info-row"><span class="info-label">Email:</span><span class="info-value">{cli_email}</span></div>
            </div>
        </div>
        
        <div class="info-grid" style="grid-template-columns: repeat(4, 1fr);">
            <div class="info-box" style="text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #0284C7;">{stats['total_pecas']}</div>
                <div style="font-size: 11px; color: #64748B;">Peças</div>
            </div>
            <div class="info-box" style="text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #16A34A;">{stats['total_area_m2']:.1f} m²</div>
                <div style="font-size: 11px; color: #64748B;">Área MDF</div>
            </div>
            <div class="info-box" style="text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #7C3AED;">{stats['total_fita_m']:.0f} m</div>
                <div style="font-size: 11px; color: #64748B;">Fita de Borda</div>
            </div>
            <div class="info-box" style="text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #DC2626;">{stats['num_ambientes']}</div>
                <div style="font-size: 11px; color: #64748B;">Ambientes</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📋 Descrição do Projeto</h2>
            <p style="color: #475569; line-height: 1.6;">
                Fornecimento e instalação de mobiliário planejado para o projeto <b>{project_name}</b>, 
                compreendendo <b>{stats['total_pecas']} peças</b> distribuídas em <b>{stats['num_ambientes']} ambiente(s)</b>, 
                totalizando <b>{stats['total_area_m2']:.2f} m²</b> de chapas de MDF/pedra.
            </p>
            <p style="color: #475569; line-height: 1.6;">
                Inclui: corte, usinagem (dobradiças, corrediças, minifix), fita de borda em todas as faces expostas, 
                ferragens padrão TrazoMob, montagem e instalação no local.
            </p>
        </div>
        
        <div class="section">
            <h2>💰 Investimento Detalhado</h2>
            <table>
                <thead>
                    <tr>
                        <th>Item / Descrição</th>
                        <th style="text-align: center;">Quantidade</th>
                        <th style="text-align: center;">Un.</th>
                        <th style="text-align: right;">Preço Unit.</th>
                        <th style="text-align: right;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {item_rows}
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>🏠 Resumo por Ambiente</h2>
            <table>
                <thead>
                    <tr>
                        <th>Ambiente</th>
                        <th style="text-align: right;">Custo Direto</th>
                        <th style="text-align: right;">Com Markup</th>
                        <th style="text-align: right;">Total Final</th>
                    </tr>
                </thead>
                <tbody>
                    {amb_rows}
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>📊 Resumo Financeiro</h2>
            <table class="totals-table">
                <tr><td>Custo Direto (materiais + mão de obra)</td><td style="text-align: right;">{formatar_moeda(orc['custo_direto'])}</td></tr>
                <tr><td>Markup ({prefs.get_markup():.0%})</td><td style="text-align: right;">{formatar_moeda(orc['markup_valor'])}</td></tr>
                <tr><td><b>Subtotal com Markup</b></td><td style="text-align: right;"><b>{formatar_moeda(orc['subtotal_com_markup'])}</b></td></tr>
                <tr><td>Impostos ({prefs.get_impostos_percent():.0%})</td><td style="text-align: right;">{formatar_moeda(orc['impostos_valor'])}</td></tr>
                <tr><td><b>Subtotal com Impostos</b></td><td style="text-align: right;"><b>{formatar_moeda(orc['subtotal_com_markup'] + orc['impostos_valor'])}</b></td></tr>
                <tr><td>Desconto ({prefs.get_desconto_percent():.0%})</td><td style="text-align: right;">-{formatar_moeda(orc['desconto_valor'])}</td></tr>
                <tr><td>Frete / Entrega</td><td style="text-align: right;">{formatar_moeda(orc['frete_valor'])}</td></tr>
                <tr><td><b>TOTAL FINAL</b></td><td style="text-align: right;"><b>{formatar_moeda(orc['total_final'])}</b></td></tr>
            </table>
        </div>
        
        <div class="validade">
            Válida até: {data_validade} (emitida em {data_emissao})
        </div>
        
        <div class="notes">
            <b>Observações & Condições:</b><br>
            {observacoes or "• Valores incluem materiais, mão de obra, ferragens padrão e instalação.<br>• Prazo de execução: a combinar após aprovação.<br>• Pagamento: 50% na assinatura, 50% na entrega.<br>• Alterações após aprovação sujeitas a reorçamento.<br>• Garantia de 12 meses contra defeitos de fabricação."}
        </div>
        
        <div class="signature">
            <div class="sig-block">
                <div class="sig-line">{emp_nome}</div>
                <div style="font-size: 11px; color: #64748B;">Responsável Técnico</div>
            </div>
            <div class="sig-block">
                <div class="sig-line">{client_name}</div>
                <div style="font-size: 11px; color: #64748B;">Cliente</div>
            </div>
        </div>
        
        <div style="text-align: center; margin-top: 40px; font-size: 11px; color: #94A3B8; border-top: 1px solid #E2E8F0; padding-top: 20px;">
            Documento gerado pelo TrazoMob — IngeTrazo | www.ingetrazo.com.br
        </div>
    </div>
</body>
</html>
"""
    
    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
    
    return html


def generate_proposal_pdf(
    parts: List[dict[str, Any]],
    filepath: str | Path,
    project_name: str = "Projeto TrazoMob",
    client_name: str = "Cliente",
    client_data: Optional[Dict[str, str]] = None,
    observacoes: str = "",
) -> bool:
    """Gera proposta em PDF usando weasyprint (se disponível) ou retorna False.
    
    Requer: pip install weasyprint
    """
    try:
        from weasyprint import HTML
        html = generate_proposal_html(
            parts=parts,
            project_name=project_name,
            client_name=client_name,
            client_data=client_data,
            observacoes=observacoes,
        )
        HTML(string=html).write_pdf(str(filepath))
        return True
    except ImportError:
        # weasyprint não instalado
        return False
    except Exception as e:
        print(f"[TrazoMob] Erro ao gerar PDF: {e}")
        return False