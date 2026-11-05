# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Otimizador paramétrico de plano de corte 2D (Guilhotina / Best-Fit Decreasing).

Agrupa peças por material e espessura, aplicando corte com espaçamento de navalha (kerf),
refilo perimetral da chapa de MDF e respeito rigoroso ao sentido do veio da madeira.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CutPiece:
    """Representa uma peça inserida ou a ser inserida no plano de corte."""
    id: int
    nome: str
    comprimento: float  # Dimensão de corte (X bruto para guilhotina)
    largura: float      # Dimensão de corte (Y bruto para guilhotina)
    espessura: float
    material: str
    comprimento_final: float = 0.0  # Medida acabada do móvel
    largura_final: float = 0.0      # Medida acabada do móvel
    espessura_fita: float = 0.45
    fita_c1: bool = False
    fita_c2: bool = False
    fita_l1: bool = False
    fita_l2: bool = False
    ignorar_veio: bool = False
    quantidade: int = 1
    operacoes: list[dict[str, Any]] = field(default_factory=list)
    # Posição calculada na chapa (em mm)
    x: float = 0.0
    y: float = 0.0
    w_aloc: float = 0.0
    h_aloc: float = 0.0
    rotacionada: bool = False


@dataclass
class SheetConfig:
    """Configurações da chapa bruta e parâmetros de corte."""
    comprimento: float = 2750.0  # X (mm)
    largura: float = 1850.0      # Y (mm)
    espessura_corte: float = 4.0  # Kerf do disco de serra (mm)
    refilo: float = 10.0         # Margem de limpeza nas bordas da chapa (mm)


@dataclass
class CutSheet:
    """Representa uma chapa individual cortada com suas peças e sobras."""
    indice: int
    material: str
    espessura: float
    comprimento_bruto: float
    largura_bruto: float
    pecas: list[CutPiece] = field(default_factory=list)
    sobras: list[tuple[float, float, float, float]] = field(default_factory=list)  # (x, y, w, h)
    area_util_mm2: float = 0.0
    aproveitamento_pct: float = 0.0
    metros_fita: float = 0.0


class GuillotineOptimizer:
    """Algoritmo de corte 2D guilhotinado com suporte a corte de serra e veio."""

    def __init__(self, config: SheetConfig | None = None) -> None:
        self.config = config or SheetConfig()

    def optimize(self, raw_parts: list[dict[str, Any]]) -> dict[str, list[CutSheet]]:
        """Otimiza a lista de peças separando por material e espessura."""
        # 1. Expande quantidades e agrupa por (material, espessura)
        grupos_material: dict[str, list[CutPiece]] = {}
        for p in raw_parts:
            qtd = int(p.get("quantidade", 1))
            mat = str(p.get("material", "MDF Branco TX 15mm"))
            esp = float(p.get("espessura", 15.0))
            chave = f"{mat} ({int(round(esp))}mm)"

            comp_final = float(p.get("comprimento", 100.0))
            larg_final = float(p.get("largura", 100.0))
            comp_corte = float(p.get("comprimento_corte") or comp_final)
            larg_corte = float(p.get("largura_corte") or larg_final)
            esp_fita = float(p.get("espessura_fita") or 0.45)

            for _ in range(qtd):
                peca = CutPiece(
                    id=int(p.get("id", 0)),
                    nome=str(p.get("nome", "Peça")),
                    comprimento=comp_corte,
                    largura=larg_corte,
                    espessura=esp,
                    material=mat,
                    comprimento_final=comp_final,
                    largura_final=larg_final,
                    espessura_fita=esp_fita,
                    fita_c1=bool(p.get("fita_c1", False)),
                    fita_c2=bool(p.get("fita_c2", False)),
                    fita_l1=bool(p.get("fita_l1", False)),
                    fita_l2=bool(p.get("fita_l2", False)),
                    ignorar_veio=bool(p.get("ignorar_veio", False)),
                    quantidade=1,
                    operacoes=list(p.get("operacoes", [])),
                )
                grupos_material.setdefault(chave, []).append(peca)

        # 2. Otimiza cada grupo de material individualmente
        resultado: dict[str, list[CutSheet]] = {}
        for mat_key, pecas in grupos_material.items():
            resultado[mat_key] = self._pack_material_group(pecas, mat_key)

        return resultado

    def _pack_material_group(self, pecas: list[CutPiece], mat_key: str) -> list[CutSheet]:
        """Empacota peças de um mesmo material nas chapas com algoritmo Maximal Rectangles / Best-Fit."""
        # Ordena peças por maior área e maior dimensão (Heurística Best-Fit Decreasing)
        pecas_ordenadas = sorted(
            pecas,
            key=lambda p: (max(p.comprimento, p.largura), p.comprimento * p.largura),
            reverse=True,
        )

        chapas: list[CutSheet] = []
        pecas_restantes = list(pecas_ordenadas)

        cfg = self.config
        kerf = cfg.espessura_corte
        refilo = cfg.refilo

        # Área útil da chapa bruta descontando refilos
        util_w = cfg.comprimento - 2 * refilo
        util_h = cfg.largura - 2 * refilo

        while pecas_restantes:
            num_chapa = len(chapas) + 1
            chapa = CutSheet(
                indice=num_chapa,
                material=mat_key,
                espessura=pecas_restantes[0].espessura if pecas_restantes else 15.0,
                comprimento_bruto=cfg.comprimento,
                largura_bruto=cfg.largura,
            )

            # Lista de retângulos livres disponíveis na chapa (x, y, w, h)
            # Inicialmente, um grande retângulo útil descontando refilo inicial
            espacos_livres: list[tuple[float, float, float, float]] = [(refilo, refilo, util_w, util_h)]
            nao_couberam: list[CutPiece] = []

            for p in pecas_restantes:
                melhor_espaco_idx = -1
                melhor_rot = False
                menor_sobra_area = float("inf")

                # Testa orientação normal (comprimento no eixo X, largura no Y)
                orientacoes = [(p.comprimento, p.largura, False)]
                # Se veio ignorado ou indiferente, pode girar 90 graus
                if p.ignorar_veio:
                    orientacoes.append((p.largura, p.comprimento, True))

                for pw, ph, rot in orientacoes:
                    for i, (fx, fy, fw, fh) in enumerate(espacos_livres):
                        if pw <= fw + 1e-4 and ph <= fh + 1e-4:
                            sobra_area = (fw * fh) - (pw * ph)
                            # Prefere o espaço mais justo (Best-Fit)
                            if sobra_area < menor_sobra_area:
                                menor_sobra_area = sobra_area
                                melhor_espaco_idx = i
                                melhor_rot = rot
                                melhor_pw, melhor_ph = pw, ph

                if melhor_espaco_idx >= 0:
                    # Encontrou espaço para alocar a peça!
                    fx, fy, fw, fh = espacos_livres.pop(melhor_espaco_idx)
                    p.x = fx
                    p.y = fy
                    p.w_aloc = melhor_pw
                    p.h_aloc = melhor_ph
                    p.rotacionada = melhor_rot
                    chapa.pecas.append(p)
                    chapa.area_util_mm2 += (p.comprimento * p.largura)

                    # Calcula fita de borda
                    if p.fita_c1: chapa.metros_fita += p.comprimento / 1000.0
                    if p.fita_c2: chapa.metros_fita += p.comprimento / 1000.0
                    if p.fita_l1: chapa.metros_fita += p.largura / 1000.0
                    if p.fita_l2: chapa.metros_fita += p.largura / 1000.0

                    # Divisão guilhotina do espaço livre restante (Split com serra kerf):
                    sobra_dir_w = fw - melhor_pw - kerf
                    sobra_dir_h = melhor_ph

                    sobra_cima_w = fw
                    sobra_cima_h = fh - melhor_ph - kerf

                    if sobra_dir_w > 15.0 and sobra_dir_h > 15.0:
                        espacos_livres.append((fx + melhor_pw + kerf, fy, sobra_dir_w, sobra_dir_h))

                    if sobra_cima_w > 15.0 and sobra_cima_h > 15.0:
                        espacos_livres.append((fx, fy + melhor_ph + kerf, sobra_cima_w, sobra_cima_h))

                    # Ordena espaços livres por menor área para manter o empacotamento denso
                    espacos_livres.sort(key=lambda s: s[2] * s[3])
                else:
                    nao_couberam.append(p)

            # Sobras aproveitáveis (retalhos maiores que 200x200mm)
            for s in espacos_livres:
                if s[2] >= 200.0 and s[3] >= 200.0:
                    chapa.sobras.append(s)

            area_bruta = cfg.comprimento * cfg.largura
            chapa.aproveitamento_pct = round((chapa.area_util_mm2 / area_bruta) * 100.0, 1)
            chapas.append(chapa)

            if len(nao_couberam) == len(pecas_restantes):
                # Caso alguma peça seja maior que a própria chapa bruta
                break
            pecas_restantes = nao_couberam

        return chapas
