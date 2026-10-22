# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Exportação de plano de corte para TrazoMob (texto tsv, CSV e JSON)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def format_trazomob_text(parts: list[dict[str, Any]]) -> str:
    """Gera texto tab-separado (TSV) pronto para colar no TrazoMob (Ctrl+V)."""
    lines = []
    for p in parts:
        qtd = p.get("quantidade", 1)
        comp = f"{p['comprimento']:.1f}"
        larg = f"{p['largura']:.1f}"
        nome = p["nome"]
        c1 = "1" if p.get("fita_c1") else "0"
        c2 = "1" if p.get("fita_c2") else "0"
        l1 = "1" if p.get("fita_l1") else "0"
        l2 = "1" if p.get("fita_l2") else "0"
        fitas = f"{c1};{c2};{l1};{l2}"
        mat = p["material"]
        veio = "S" if p.get("ignorar_veio") else "N"
        lines.append(f"{qtd}\t{comp}\t{larg}\t{nome}\t{fitas}\t{mat}\t{veio}")
    return "\n".join(lines)


def export_trazomob_csv(parts: list[dict[str, Any]], filepath: str | Path) -> None:
    """Salva lista de peças em arquivo CSV compatível com TrazoMob com resumo de usinagens."""
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "Quantidade", "Comprimento Final", "Largura Final", "Comp Corte Bruto", "Larg Corte Bruto",
            "Espessura", "Descricao", "Material",
            "Espessura Fita", "Fita C1", "Fita C2", "Fita L1", "Fita L2", "Ignorar Veio", "Furações / Usinagens"
        ])
        for p in parts:
            ops = p.get("operacoes", [])
            ops_desc = "; ".join(o.get("descricao", "") for o in ops if o.get("descricao")) if ops else "NENHUMA"
            comp_c = p.get("comprimento_corte", p["comprimento"])
            larg_c = p.get("largura_corte", p["largura"])
            esp_f = p.get("espessura_fita", 0.45)
            writer.writerow([
                p.get("quantidade", 1), f"{p['comprimento']:.1f}", f"{p['largura']:.1f}",
                f"{comp_c:.1f}", f"{larg_c:.1f}", f"{p['espessura']:.1f}",
                p["nome"], p["material"],
                f"{esp_f:.2f}",
                "SIM" if p.get("fita_c1") else "NAO", "SIM" if p.get("fita_c2") else "NAO",
                "SIM" if p.get("fita_l1") else "NAO", "SIM" if p.get("fita_l2") else "NAO",
                "SIM" if p.get("ignorar_veio") else "NAO",
                ops_desc,
            ])


def export_trazomob_json(parts: list[dict[str, Any]], filepath: str | Path) -> None:
    """Salva lista de peças em arquivo JSON estruturado com metadados e usinagens detalhadas."""
    clean_data = [dict(p) for p in parts]
    for p in clean_data:
        p.pop("group", None)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generator": "IngeTrazo TrazoMob",
                "version": "2.0",
                "parts": clean_data,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

