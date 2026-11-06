# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Construtor especializado para peças avulsas e tampos engrossados de marcenaria."""
from __future__ import annotations

from typing import Optional, List, Tuple
from core.group import Group
from ..builders.mesh_utils import create_board_group
from ..domain.materials_catalog import ALL_BOX_MATERIALS, MDF_MATERIALS


class CustomPartsBuilder:
    """Construtor desacoplado para tampos engrossados e peças avulsas individuais."""

    @staticmethod
    def get_material_color(material: str) -> tuple[float, float, float]:
        from ..domain.materials_catalog import get_material_color
        return get_material_color(material)

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

    @classmethod
    def build_portas_correr_avulsas(
        cls,
        largura_mm: float,
        altura_mm: float,
        prof_mm: float = 65.0,
        num_portas: int = 2,
        esp_mm: float = 15.0,
        transpasse_mm: float = 30.0,
        material: str = "MDF Branco TX 15mm",
        material_fita: Optional[str] = None,
        offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        puxador_tipo: str = "perfil",
        puxador_cor: str = "preto",
        puxador_pos: str = "padrao",
        desconto_perfil_mm: float = 35.0,
        perfil_modelo: str = "gola",
    ) -> List[Group]:
        """Gera um conjunto avulso de portas de correr (2 a 4 portas) com trilhos duplos de alumínio."""
        from PySide6.QtGui import QVector3D

        ox, oy, oz = offset
        L = max(0.40, float(largura_mm) / 1000.0)
        A = max(0.30, float(altura_mm) / 1000.0)
        P = max(0.045, float(prof_mm) / 1000.0)
        E_frente = max(0.006, float(esp_mm) / 1000.0)
        n_portas = max(2, min(4, int(num_portas)))
        transpasse = max(0.0, float(transpasse_mm) / 1000.0)

        cor_frente = cls.get_material_color(material)
        cor_fita = cls.get_material_color(material_fita) if material_fita else None

        groups: List[Group] = []

        # 1. Trilhos Duplos de Alumínio (Inferior e Superior)
        prof_trilho = min(0.045, P)
        groups.append(create_board_group(
            "Portas Correr - Trilho Inferior",
            (ox, oy, oz),
            (L, prof_trilho, 0.008),
            "Alumínio Anodizado", color=(0.75, 0.77, 0.80),
        ))
        groups.append(create_board_group(
            "Portas Correr - Trilho Superior",
            (ox, oy, oz + A - 0.035),
            (L, prof_trilho, 0.035),
            "Alumínio Anodizado", color=(0.75, 0.77, 0.80),
        ))

        # 2. Cálculo de corte das folhas (2, 3 ou 4 portas)
        # Em portas de correr, quando puxador_pos é "padrao"/"auto"/"superior" e puxador_tipo é "perfil" ou "alca",
        # o puxador/perfil de porta de correr fica na lateral/extensão vertical da folha.
        eff_pux_pos = puxador_pos
        if str(eff_pux_pos or "padrao").lower() in ("padrao", "auto", "superior", "topo"):
            eff_pux_pos = "extensao"
        # Desconto vertical padrão de 15mm para sistema de correr/roldanas
        alt_porta = max(0.10, A - 0.015)
        z_porta = oz + 0.008
        # No sistema de coordenadas do TrazoMob, a frente do móvel aponta para -Y e o fundo para +Y.
        # Logo, o trilho externo (frontal) fica em menor Y e o trilho interno (traseiro) em maior Y.
        y_trilho_frontal = oy + 0.004
        y_trilho_traseiro = oy + 0.004 + E_frente + 0.012

        if n_portas == 2:
            # 2 Portas: 1 transpasse central (30mm)
            larg_porta = (L + transpasse) / 2.0
            slide_dist = max(0.05, larg_porta - transpasse)

            # Folha 1: Esquerda (Trilho Traseiro/Interno) -> corre para a direita (+X)
            # Puxador na borda esquerda externa (door_side="right" coloca o puxador em ox)
            p1 = create_board_group(
                "Porta Correr 1 - Esq (Interna)",
                (ox, y_trilho_traseiro, z_porta),
                (larg_porta, E_frente, alt_porta),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor_frente, material_fita=material_fita, cor_fita=cor_fita,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=eff_pux_pos,
                desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                door_side="right",
            )
            if getattr(p1, "ext", None) is None:
                p1.ext = {}
            p1.ext["slide_axis"] = QVector3D(1.0, 0.0, 0.0)
            p1.ext["slide_distance"] = float(slide_dist)
            groups.append(p1)

            # Folha 2: Direita (Trilho Frontal/Externo) -> corre para a esquerda (-X)
            # Puxador na borda direita externa (door_side="left" coloca o puxador em ox + larg_porta)
            x_p2 = ox + L - larg_porta
            p2 = create_board_group(
                "Porta Correr 2 - Dir (Externa)",
                (x_p2, y_trilho_frontal, z_porta),
                (larg_porta, E_frente, alt_porta),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor_frente, material_fita=material_fita, cor_fita=cor_fita,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=eff_pux_pos,
                desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                door_side="left",
            )
            if getattr(p2, "ext", None) is None:
                p2.ext = {}
            p2.ext["slide_axis"] = QVector3D(-1.0, 0.0, 0.0)
            p2.ext["slide_distance"] = float(slide_dist)
            groups.append(p2)

        elif n_portas == 3:
            # 3 Portas: 2 transpasses (30mm entre F1-F2 e 30mm entre F2-F3)
            larg_porta = (L + (2.0 * transpasse)) / 3.0
            slide_dist = max(0.05, larg_porta - transpasse)

            # Folha 1: Esquerda (Trilho Traseiro/Interno) -> corre para a direita (+X), puxador na esquerda
            p1 = create_board_group(
                "Porta Correr 1 - Esq (Interna)",
                (ox, y_trilho_traseiro, z_porta),
                (larg_porta, E_frente, alt_porta),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor_frente, material_fita=material_fita, cor_fita=cor_fita,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=eff_pux_pos,
                desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                door_side="right",
            )
            if getattr(p1, "ext", None) is None:
                p1.ext = {}
            p1.ext["slide_axis"] = QVector3D(1.0, 0.0, 0.0)
            p1.ext["slide_distance"] = float(slide_dist)
            groups.append(p1)

            # Folha 2: Centro (Trilho Frontal/Externo) -> corre para os dois lados, puxador nos dois lados ("both")
            x_p2 = ox + (L * 0.5) - (larg_porta * 0.5)
            p2 = create_board_group(
                "Porta Correr 2 - Centro (Externa)",
                (x_p2, y_trilho_frontal, z_porta),
                (larg_porta, E_frente, alt_porta),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor_frente, material_fita=material_fita, cor_fita=cor_fita,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=eff_pux_pos,
                desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                door_side="both",
            )
            if getattr(p2, "ext", None) is None:
                p2.ext = {}
            p2.ext["slide_axis"] = QVector3D(1.0, 0.0, 0.0)
            p2.ext["slide_distance"] = float(slide_dist)
            groups.append(p2)

            # Folha 3: Direita (Trilho Traseiro/Interno) -> corre para a esquerda (-X), puxador na direita
            x_p3 = ox + L - larg_porta
            p3 = create_board_group(
                "Porta Correr 3 - Dir (Interna)",
                (x_p3, y_trilho_traseiro, z_porta),
                (larg_porta, E_frente, alt_porta),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor_frente, material_fita=material_fita, cor_fita=cor_fita,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=eff_pux_pos,
                desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                door_side="left",
            )
            if getattr(p3, "ext", None) is None:
                p3.ext = {}
            p3.ext["slide_axis"] = QVector3D(-1.0, 0.0, 0.0)
            p3.ext["slide_distance"] = float(slide_dist)
            groups.append(p3)

        else:
            # 4 Portas: sistema simétrico (2 laterais internas no trilho traseiro + 2 centrais externas no trilho frontal)
            larg_porta = (L + (2.0 * transpasse)) / 4.0
            slide_dist = max(0.05, larg_porta - transpasse)

            # Folha 1: Canto Esquerdo (Traseira/Interna) -> corre para a direita (+X), puxador na esquerda
            x_p1 = ox
            p1 = create_board_group(
                "Porta Correr 1 - Esq (Interna)",
                (x_p1, y_trilho_traseiro, z_porta),
                (larg_porta, E_frente, alt_porta),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor_frente, material_fita=material_fita, cor_fita=cor_fita,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=eff_pux_pos,
                desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                door_side="right",
            )
            if getattr(p1, "ext", None) is None:
                p1.ext = {}
            p1.ext["slide_axis"] = QVector3D(1.0, 0.0, 0.0)
            p1.ext["slide_distance"] = float(slide_dist)
            groups.append(p1)

            # Folha 2: Centro-Esquerda (Frontal/Externa) -> corre para a esquerda (-X), puxador no encontro central (direita)
            x_p2 = ox + (L * 0.5) - larg_porta
            p2 = create_board_group(
                "Porta Correr 2 - Centro Esq (Externa)",
                (x_p2, y_trilho_frontal, z_porta),
                (larg_porta, E_frente, alt_porta),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor_frente, material_fita=material_fita, cor_fita=cor_fita,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=eff_pux_pos,
                desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                door_side="left",
            )
            if getattr(p2, "ext", None) is None:
                p2.ext = {}
            p2.ext["slide_axis"] = QVector3D(-1.0, 0.0, 0.0)
            p2.ext["slide_distance"] = float(slide_dist)
            groups.append(p2)

            # Folha 3: Centro-Direita (Frontal/Externa) -> corre para a direita (+X), puxador no encontro central (esquerda)
            x_p3 = ox + (L * 0.5)
            p3 = create_board_group(
                "Porta Correr 3 - Centro Dir (Externa)",
                (x_p3, y_trilho_frontal, z_porta),
                (larg_porta, E_frente, alt_porta),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor_frente, material_fita=material_fita, cor_fita=cor_fita,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=eff_pux_pos,
                desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                door_side="right",
            )
            if getattr(p3, "ext", None) is None:
                p3.ext = {}
            p3.ext["slide_axis"] = QVector3D(1.0, 0.0, 0.0)
            p3.ext["slide_distance"] = float(slide_dist)
            groups.append(p3)

            # Folha 4: Canto Direito (Traseira/Interna) -> corre para a esquerda (-X), puxador na direita
            x_p4 = ox + L - larg_porta
            p4 = create_board_group(
                "Porta Correr 4 - Dir (Interna)",
                (x_p4, y_trilho_traseiro, z_porta),
                (larg_porta, E_frente, alt_porta),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                color=cor_frente, material_fita=material_fita, cor_fita=cor_fita,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=eff_pux_pos,
                desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                door_side="left",
            )
            if getattr(p4, "ext", None) is None:
                p4.ext = {}
            p4.ext["slide_axis"] = QVector3D(-1.0, 0.0, 0.0)
            p4.ext["slide_distance"] = float(slide_dist)
            groups.append(p4)

        return groups




