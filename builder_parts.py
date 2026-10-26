# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Construtor especializado para peças avulsas e tampos engrossados de marcenaria."""
from __future__ import annotations

from typing import Optional, List, Tuple
from core.group import Group
from .builder_mesh_utils import create_board_group
from .materials_catalog import ALL_BOX_MATERIALS, MDF_MATERIALS


class CustomPartsBuilder:
    """Construtor desacoplado para tampos engrossados e peças avulsas individuais."""

    @staticmethod
    def get_material_color(material: str) -> tuple[float, float, float]:
        from .builder import CabinetBuilder
        return CabinetBuilder.get_material_color(material)

    @classmethod
    def build_peca_avulsa(
        cls,
        subtipo: str,
        largura_mm: float,
        altura_mm: float,
        prof_mm: float,
        esp_mm: float = 15.0,
        material: str = "MDF Branco TX 15mm",
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        material_fita: str | None = None,
        puxador_tipo: str = "alca",
        puxador_cor: str = "preto",
        puxador_pos: str = "padrao",
        desconto_perfil_mm: float = 35.0,
        perfil_modelo: str = "gola",
    ) -> list[Group]:
        """Gera uma peça avulsa individual (lateral, base, travessa, fundo, porta, etc.)."""
        ox, oy, oz = offset
        L = largura_mm / 1000.0
        A = altura_mm / 1000.0
        P = prof_mm / 1000.0
        E = esp_mm / 1000.0

        cor = cls.get_material_color(material)
        cor_fita = cls.get_material_color(material_fita) if material_fita else None

        groups: list[Group] = []

        if subtipo == "lateral":
            # Lateral vertical em YZ (espessura ao longo de X = E, profundidade = P, altura = A)
            groups.append(create_board_group(
                "Lateral Avulsa",
                (ox, oy, oz),
                (E, P, A),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor, material_fita=material_fita, cor_fita=cor_fita,
            ))
        elif subtipo in ("base", "prateleira"):
            # Chapa horizontal em XY (largura = L, profundidade = P, espessura ao longo de Z = E)
            nome = "Base Avulsa" if subtipo == "base" else "Prateleira Avulsa"
            groups.append(create_board_group(
                nome,
                (ox, oy, oz),
                (L, P, E),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor, material_fita=material_fita, cor_fita=cor_fita,
            ))
        elif subtipo == "travessa_deitada":
            # Régua deitada horizontal (largura = L, profundidade = P, espessura ao longo de Z = E)
            groups.append(create_board_group(
                "Travessa Deitada",
                (ox, oy, oz),
                (L, P, E),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor, material_fita=material_fita, cor_fita=cor_fita,
            ))
        elif subtipo == "travessa_em_pe":
            # Régua em pé vertical (largura = L, espessura ao longo de Y = E, altura = A)
            groups.append(create_board_group(
                "Travessa em Pe",
                (ox, oy, oz),
                (L, E, A),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor, material_fita=material_fita, cor_fita=cor_fita,
            ))
        elif subtipo == "pilar_quina":
            # Régua de coluna vertical (largura = L, espessura ao longo de Y = E, altura = A)
            groups.append(create_board_group(
                "Pilar de Quina",
                (ox, oy, oz),
                (L, E, A),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor, material_fita=material_fita, cor_fita=cor_fita,
            ))
        elif subtipo == "fundo":
            # Fundo vertical traseiro (largura = L, espessura ao longo de Y = E ou fundo, altura = A)
            esp_f = E if E <= 0.010 else 0.006
            groups.append(create_board_group(
                "Fundo Avulso",
                (ox, oy, oz),
                (L, esp_f, A),
                material, color=cor,
            ))
        elif subtipo == "porta":
            # Porta / Frente frontal (largura = L, espessura ao longo de Y = E, altura = A)
            groups.append(create_board_group(
                "Porta Avulsa",
                (ox, oy, oz),
                (L, E, A),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor, material_fita=material_fita, cor_fita=cor_fita,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos,
                desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                door_side="single", is_upper=False,
            ))

        else:
            groups.append(create_board_group(
                f"Peca {subtipo}",
                (ox, oy, oz),
                (L, P, A),
                material, fita_c1=True, color=cor,
            ))

        return groups

    @classmethod
    def build_tampo_engrossado(
        cls,
        L_mm: float,
        A_mm: float,
        P_mm: float,
        esp_chapa_mm: float = 18.0,
        larg_engrosso_mm: float = 70.0,
        tipo_engrosso: str = "3_lados",
        qtd_engrosso: int = 1,
        fechar_embaixo: bool = False,
        material: str = "MDF Branco TX",
        material_fita: Optional[str] = None,
        offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> List[Group]:
        """Gera um tampo engrossado de marcenaria com réguas perimetrais na espessura real da chapa."""
        ox, oy, oz = offset
        L = L_mm / 1000.0
        P = P_mm / 1000.0

        # Espessura nominal da madeira
        e_chapa = (esp_chapa_mm if esp_chapa_mm > 0 else 18.0) / 1000.0

        # Determina a quantidade de camadas de réguas de engrosso no meio:
        # Se qtd_engrosso for passado explicitamente (> 0), usa-o diretamente.
        n_camadas = int(qtd_engrosso) if qtd_engrosso and int(qtd_engrosso) >= 1 else 1

        w_regua = (larg_engrosso_mm if larg_engrosso_mm > 0 else 70.0) / 1000.0
        w_regua = min(w_regua, min(L, P) * 0.45)

        cor = cls.get_material_color(material)
        cor_fita = cls.get_material_color(material_fita) if material_fita else None

        groups: List[Group] = []

        # ── ESTRUTURA VERTICAL DE BAIXO PARA CIMA: ──────────────────
        # Nível inferior do módulo completo começa em oz:
        # 1. Se 'fechar_embaixo' estiver ativo:
        #    - A chapa de fechamento inferior fica na base: z = oz até oz + e_chapa.
        #    - As réguas de engrosso ficam sobre ela: z = oz + e_chapa + (idx * e_chapa).
        #    - A chapa superior fica no topo de tudo: z = oz + e_chapa + (n_camadas * e_chapa).
        # 2. Se NÃO houver fechamento inferior:
        #    - As réguas de engrosso ficam na base: z = oz + (idx * e_chapa).
        #    - A chapa superior fica no topo: z = oz + (n_camadas * e_chapa).

        z_base_reguas = oz + (e_chapa if fechar_embaixo else 0.0)
        z_tampo_topo = z_base_reguas + n_camadas * e_chapa

        # 1. Chapa Superior Principal (Fica no topo em z_tampo_topo)
        grp_tampo = create_board_group(
            "Tampo Superior",
            (ox, oy, z_tampo_topo),
            (L, P, e_chapa),
            material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
            color=cor, material_fita=material_fita, cor_fita=cor_fita,
        )
        groups.append(grp_tampo)

        # 2. Réguas Intermediárias de Engrosso em Fatias/Camadas Discretas
        # Cada camada tem espessura exatamente igual a 'e_chapa' da madeira
        for camada_idx in range(n_camadas):
            z_layer = z_base_reguas + camada_idx * e_chapa
            sufixo_camada = f" Camada {camada_idx + 1}" if n_camadas > 1 else ""

            # Régua Frontal (ao longo de X)
            grp_regua_front = create_board_group(
                f"Régua Engrosso Frontal{sufixo_camada}",
                (ox, oy, z_layer),
                (L, w_regua, e_chapa),
                material, fita_c1=True, fita_c2=False, fita_l1=True, fita_l2=True,
                color=cor, material_fita=material_fita, cor_fita=cor_fita,
            )
            groups.append(grp_regua_front)

            # Réguas Laterais (ao longo de Y)
            if tipo_engrosso in ("3_lados", "4_lados", "laterais"):
                y_lat_inicio = oy + w_regua
                comp_lat = P - w_regua - (w_regua if tipo_engrosso == "4_lados" else 0.0)
                if comp_lat > 0.02:
                    # Lateral Esquerda
                    grp_lat_esq = create_board_group(
                        f"Régua Engrosso Lateral Esquerda{sufixo_camada}",
                        (ox, y_lat_inicio, z_layer),
                        (w_regua, comp_lat, e_chapa),
                        material, fita_c1=False, fita_c2=False, fita_l1=True, fita_l2=False,
                        color=cor, material_fita=material_fita, cor_fita=cor_fita,
                    )
                    groups.append(grp_lat_esq)

                    # Lateral Direita
                    grp_lat_dir = create_board_group(
                        f"Régua Engrosso Lateral Direita{sufixo_camada}",
                        (ox + L - w_regua, y_lat_inicio, z_layer),
                        (w_regua, comp_lat, e_chapa),
                        material, fita_c1=False, fita_c2=False, fita_l1=False, fita_l2=True,
                        color=cor, material_fita=material_fita, cor_fita=cor_fita,
                    )
                    groups.append(grp_lat_dir)

            # Régua Traseira (ao longo de X, se 4 lados)
            if tipo_engrosso == "4_lados":
                grp_regua_tras = create_board_group(
                    f"Régua Engrosso Traseira{sufixo_camada}",
                    (ox, oy + P - w_regua, z_layer),
                    (L, w_regua, e_chapa),
                    material, fita_c1=False, fita_c2=True, fita_l1=True, fita_l2=True,
                    color=cor, material_fita=material_fita, cor_fita=cor_fita,
                )
                groups.append(grp_regua_tras)

            # Travessa Central de Apoio (se vão livre L > 900 mm)
            if L > 0.90:
                y_centro_inicio = oy + w_regua
                comp_centro = P - w_regua - (w_regua if tipo_engrosso == "4_lados" else 0.0)
                if comp_centro > 0.05:
                    x_centro = ox + (L - w_regua) * 0.5
                    grp_centro = create_board_group(
                        f"Régua Reforço Central{sufixo_camada}",
                        (x_centro, y_centro_inicio, z_layer),
                        (w_regua, comp_centro, e_chapa),
                        material, fita_c1=False, fita_c2=False, fita_l1=False, fita_l2=False,
                        color=cor, material_fita=material_fita, cor_fita=cor_fita,
                    )
                    groups.append(grp_centro)

        # 3. Chapa de Fechamento Inferior (Tampo Sanduíche / Tamburato)
        if fechar_embaixo:
            # Chapa inferior inteiriça na base absoluta (oz)
            grp_fechamento = create_board_group(
                "Chapa Fechamento Inferior",
                (ox, oy, oz),
                (L, P, e_chapa),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor, material_fita=material_fita, cor_fita=cor_fita,
            )
            groups.append(grp_fechamento)

        return groups




