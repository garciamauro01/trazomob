# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Estrutura e gerador de operações de furação e usinagem para marcenaria (TrazoMob).

Fornece modelos padronizados de operações:
- Furo passante / cego (caneco de dobradiça 35mm, calço, minifix, cavilha, confirmação)
- Canal / rasgo de fundo (fundo rebaixado ou ranhurado de 6mm)
- Furação de corrediças telescópicas e invisíveis (Sistema 32)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

FaceType = Literal["frontal", "traseira", "topo", "base", "esquerda", "direita"]
OpType = Literal["furo", "rasgo", "rebaixo"]


@dataclass
class MachiningOp:
    """Representa uma usinagem ou furação individual em uma chapa de marcenaria."""
    tipo: OpType
    face: FaceType
    x: float             # Distância em mm a partir da origem da face (eixo longitudinal)
    y: float             # Distância em mm a partir da origem da face (eixo transversal)
    diametro: float = 0.0      # Diâmetro em mm (para furos)
    profundidade: float = 0.0  # Profundidade em mm (se 0 ou >= espessura, furo passante)
    largura: float = 0.0       # Largura do rasgo (ex: 6.0 mm para canal de fundo)
    comprimento: float = 0.0   # Comprimento do rasgo
    descricao: str = ""        # Rótulo explicativo (ex: "Caneco Dobradiça 35mm", "Minifix")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tipo": self.tipo,
            "face": self.face,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "diametro": round(self.diametro, 2),
            "profundidade": round(self.profundidade, 2),
            "largura": round(self.largura, 2),
            "comprimento": round(self.comprimento, 2),
            "descricao": self.descricao,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MachiningOp:
        return cls(
            tipo=data.get("tipo", "furo"),
            face=data.get("face", "frontal"),
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            diametro=float(data.get("diametro", 0.0)),
            profundidade=float(data.get("profundidade", 0.0)),
            largura=float(data.get("largura", 0.0)),
            comprimento=float(data.get("comprimento", 0.0)),
            descricao=str(data.get("descricao", "")),
        )


def make_hinge_cup_holes(
    altura_porta_mm: float,
    recuo_centro_borda_mm: float = 21.5,
    afastamento_topo_base_mm: float = 100.0,
    face: FaceType = "traseira",
    num_dobradicas: int | None = None,
) -> list[MachiningOp]:
    """Gera furos tipo caneco de dobradiça (Ø 35mm, prof. 12mm) para portas de marcenaria."""
    if num_dobradicas is None:
        if altura_porta_mm < 900:
            n = 2
        elif altura_porta_mm < 1600:
            n = 3
        elif altura_porta_mm < 2100:
            n = 4
        else:
            n = 5
    else:
        n = max(2, num_dobradicas)

    ops: list[MachiningOp] = []
    # Posições ao longo da altura da porta
    y_pos: list[float] = []
    if n == 2:
        y_pos = [afastamento_topo_base_mm, altura_porta_mm - afastamento_topo_base_mm]
    else:
        y_pos = [afastamento_topo_base_mm]
        passo = (altura_porta_mm - 2 * afastamento_topo_base_mm) / (n - 1)
        for i in range(1, n - 1):
            y_pos.append(afastamento_topo_base_mm + i * passo)
        y_pos.append(altura_porta_mm - afastamento_topo_base_mm)

    for idx, pos_y in enumerate(y_pos, 1):
        # Furo central caneco Ø 35mm
        ops.append(MachiningOp(
            tipo="furo",
            face=face,
            x=recuo_centro_borda_mm,
            y=pos_y,
            diametro=35.0,
            profundidade=12.0,
            descricao=f"Caneco Dobradiça {idx} (Ø35mm)",
        ))
        # Furos auxiliares para parafusos da dobradiça (Ø 2mm ou 5mm com entre-furos 45mm/48mm)
        ops.append(MachiningOp(
            tipo="furo",
            face=face,
            x=recuo_centro_borda_mm + 9.5,
            y=pos_y - 22.5,
            diametro=2.5,
            profundidade=10.0,
            descricao=f"Parafuso Dobradiça {idx}A",
        ))
        ops.append(MachiningOp(
            tipo="furo",
            face=face,
            x=recuo_centro_borda_mm + 9.5,
            y=pos_y + 22.5,
            diametro=2.5,
            profundidade=10.0,
            descricao=f"Parafuso Dobradiça {idx}B",
        ))

    return ops


def make_hinge_plate_holes(
    posicoes_y_mm: list[float],
    recuo_borda_frontal_mm: float = 37.0,
    face: FaceType = "traseira",
) -> list[MachiningOp]:
    """Gera furos para calço da dobradiça na lateral do móvel (Sistema 32, entre-furos 32mm)."""
    ops: list[MachiningOp] = []
    for idx, pos_y in enumerate(posicoes_y_mm, 1):
        ops.append(MachiningOp(
            tipo="furo",
            face=face,
            x=recuo_borda_frontal_mm,
            y=pos_y - 16.0,
            diametro=5.0,
            profundidade=11.5,
            descricao=f"Calço Dobradiça {idx}A (Ø5mm)",
        ))
        ops.append(MachiningOp(
            tipo="furo",
            face=face,
            x=recuo_borda_frontal_mm,
            y=pos_y + 16.0,
            diametro=5.0,
            profundidade=11.5,
            descricao=f"Calço Dobradiça {idx}B (Ø5mm)",
        ))
    return ops


def make_slide_runner_holes(
    alturas_gavetas_mm: list[float],
    profundidade_lateral_mm: float,
    recuo_frontal_mm: float = 37.0,
    face: FaceType = "traseira",
) -> list[MachiningOp]:
    """Gera furações de corrediças telescópicas (linha Sistema 32) na lateral do armário."""
    ops: list[MachiningOp] = []
    for idx, alt_y in enumerate(alturas_gavetas_mm, 1):
        # Primeiro furo (37mm da frente)
        ops.append(MachiningOp(
            tipo="furo",
            face=face,
            x=recuo_frontal_mm,
            y=alt_y,
            diametro=5.0,
            profundidade=12.0,
            descricao=f"Corrediça Gaveta {idx} - Furo Frontal (Ø5mm)",
        ))
        # Segundo furo (sistema 32: múltiplos de 32mm ou ponto intermediário)
        x_inter = recuo_frontal_mm + 128.0
        if x_inter < profundidade_lateral_mm - 50:
            ops.append(MachiningOp(
                tipo="furo",
                face=face,
                x=x_inter,
                y=alt_y,
                diametro=5.0,
                profundidade=12.0,
                descricao=f"Corrediça Gaveta {idx} - Furo Médio (Ø5mm)",
            ))
        # Furo traseiro
        x_tras = profundidade_lateral_mm - 64.0
        if x_tras > x_inter:
            ops.append(MachiningOp(
                tipo="furo",
                face=face,
                x=x_tras,
                y=alt_y,
                diametro=5.0,
                profundidade=12.0,
                descricao=f"Corrediça Gaveta {idx} - Furo Traseiro (Ø5mm)",
            ))
    return ops


def make_cabinet_joint_holes(
    comprimento_junta_mm: float,
    posicao_borda_mm: float = 9.0,  # Centro de chapa 18mm ou 15mm
    face: FaceType = "traseira",
    usar_minifix: bool = True,
) -> list[MachiningOp]:
    """Gera furações de junção topo-borda (cavilha Ø8mm e minifix Ø15mm ou confirmat)."""
    ops: list[MachiningOp] = []
    # Posiciona conectores a 50mm de cada extremidade
    pontos_x = [50.0, comprimento_junta_mm - 50.0]
    if comprimento_junta_mm > 600:
        pontos_x.insert(1, comprimento_junta_mm / 2.0)

    for idx, px in enumerate(pontos_x, 1):
        if usar_minifix:
            # Furo tambor Minifix (Ø 15mm, centro a 34mm da borda)
            ops.append(MachiningOp(
                tipo="furo",
                face=face,
                x=px,
                y=34.0,
                diametro=15.0,
                profundidade=12.5,
                descricao=f"Tambor Minifix {idx} (Ø15mm)",
            ))
        # Cavilha de alinhamento adjacente (+32mm no passo 32)
        ops.append(MachiningOp(
            tipo="furo",
            face=face,
            x=px + 32.0 if px + 32.0 < comprimento_junta_mm - 15 else px - 32.0,
            y=posicao_borda_mm,
            diametro=8.0,
            profundidade=12.0,
            descricao=f"Cavilha de Junção {idx} (Ø8mm)",
        ))
    return ops


def make_stretcher_joint_holes(
    largura_travessa_mm: float,
    esp_travessa_mm: float = 15.0,
    face: FaceType = "traseira",
    usar_minifix: bool = True,
    comprimento_travessa_mm: float = 0.0,
    eh_travessa: bool = True,
) -> list[MachiningOp]:
    """Gera operações de furação técnica para fixação de travessas estruturais (topo ou laterais).

    Para as próprias travessas (eh_travessa=True):
    - Furações de fixação em ambas as pontas (extremidade esquerda e direita):
      * Minifix (Ø15mm a 34mm do topo/borda de topo) e cavilhas (Ø8mm).
    Para as laterais da caixa (eh_travessa=False):
    - Furos de passagem / parafusos / cavilhas correspondentes nas laterais.
    """
    ops: list[MachiningOp] = []
    meio_larg = largura_travessa_mm / 2.0

    if eh_travessa and comprimento_travessa_mm > 0:
        # Furações nas duas extremidades da travessa (x próximo de 0 e x próximo do final)
        pontas_x = [34.0, comprimento_travessa_mm - 34.0]
        for idx, px in enumerate(pontas_x, 1):
            if usar_minifix:
                ops.append(MachiningOp(
                    tipo="furo",
                    face=face,
                    x=px,
                    y=meio_larg,
                    diametro=15.0,
                    profundidade=12.5,
                    descricao=f"Tambor Minifix Travessa Ponta {idx} (Ø15mm)",
                ))
            # Furo de cavilha
            dist_cav = 32.0 if idx == 1 else -32.0
            ops.append(MachiningOp(
                tipo="furo",
                face=face,
                x=px + dist_cav,
                y=meio_larg,
                diametro=8.0,
                profundidade=12.0,
                descricao=f"Cavilha Travessa Ponta {idx} (Ø8mm)",
            ))
    else:
        # Usinagem na junta / lateral
        if usar_minifix:
            ops.append(MachiningOp(
                tipo="furo",
                face=face,
                x=meio_larg,
                y=34.0,
                diametro=15.0,
                profundidade=12.5,
                descricao="Furo Conexão Travessa (Minifix Ø15mm)",
            ))
        ops.append(MachiningOp(
            tipo="furo",
            face=face,
            x=meio_larg,
            y=esp_travessa_mm / 2.0,
            diametro=8.0,
            profundidade=12.0,
            descricao="Cavilha Junção Travessa (Ø8mm)",
        ))

    return ops


def make_back_panel_groove(
    comprimento_mm: float,
    afastamento_traseiro_mm: float = 15.0,
    largura_canal_mm: float = 6.0,
    profundidade_canal_mm: float = 8.0,
    face: FaceType = "traseira",
) -> MachiningOp:
    """Gera operação de rasgo / canal para encaixe do fundo de 6mm."""
    return MachiningOp(
        tipo="rasgo",
        face=face,
        x=0.0,
        y=afastamento_traseiro_mm,
        largura=largura_canal_mm,
        comprimento=comprimento_mm,
        profundidade=profundidade_canal_mm,
        descricao=f"Canal de Fundo {largura_canal_mm:.0f}mm (Prof. {profundidade_canal_mm:.0f}mm)",
    )
