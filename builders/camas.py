# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Construtor parametrico 3D de camas planejadas (CamaBuilder).

Modelos implementados:
1. build_cama_gaveteiros: Cama plataforma com gavetoes embutidos (2 a 4 gavetas).
2. build_cama_bau: Cama box com baú fechado e estrado basculante superior.
3. build_cama_cabeceira: Cama com painel de cabeceira traseiro integrado e mesinhas laterais.
4. build_bicama: Cama solteiro com gavetão cama auxiliar deslizante inferior.
5. build_beliche: Beliche planejado com 2 leitos, guarda-corpo de proteção e escada lateral.
"""
from __future__ import annotations

import math
from typing import Any

from PySide6.QtGui import QVector3D

from core.group import Group
from ..builders.mesh_utils import create_board_group


class CamaBuilder:
    """Construtor de camas e beliches de marcenaria sob medida."""

    # -------------------------------------------------------------------------
    # 1. CAMA COM GAVETEIROS LATERAIS
    # -------------------------------------------------------------------------
    @classmethod
    def build_cama_gaveteiros(
        cls,
        largura: float = 1400.0,      # Largura externa (ex: casal ~1400)
        comprimento: float = 1950.0,  # Profundidade/Comprimento externo (Y)
        altura: float = 400.0,        # Altura do estrado/caixa (Z)
        espessura: float = 18.0,      # Espessura das chapas estruturais
        num_gavetoes: int = 4,        # 2 ou 4 gavetas laterais
        lado_gavetas: str = "ambos",  # "ambos", "esquerda", "direita"
        has_estrado: bool = True,
        material: str = "MDF Carvalho",
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        **params: Any,
    ) -> list[Group]:
        """Cama box plataforma com gavetoes laterais e divisórias estruturais de sustentacao."""
        if 'profundidade' in params and params['profundidade']:
            comprimento = float(params['profundidade'])
        if 'altura' in params and params['altura']:
            altura = float(params['altura'])
        if 'largura' in params and params['largura']:
            largura = float(params['largura'])

        E = float(espessura)
        L = float(largura)
        C = float(comprimento)
        H = float(altura)
        num_gav = int(params.get("num_gavetas", num_gavetoes))
        ox, oy, oz = offset

        groups: list[Group] = []

        # 1. Peseira (frontal Y=0) e Cabeceira da caixa (traseira Y=C-E)
        groups.append(create_board_group(
            "Cama - Peseira",
            (ox, oy, oz),
            (L, E, H),
            material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True
        ))

        groups.append(create_board_group(
            "Cama - Cabeceira Caixa",
            (ox, oy + C - E, oz),
            (L, E, H),
            material, fita_c1=True, fita_l1=True, fita_l2=True
        ))

        # 2. Longarinas / Divisória Central de Sustentação do Peso (ao longo de Y)
        dist_y_int = C - 2 * E
        groups.append(create_board_group(
            "Cama - Longarina Central",
            (ox + (L - E) / 2.0, oy + E, oz),
            (E, dist_y_int, H),
            material, fita_c1=True
        ))

        # 3. Laterais externas
        groups.append(create_board_group(
            "Cama - Lateral Esquerda",
            (ox, oy + E, oz),
            (E, dist_y_int, H),
            material, fita_c1=True, fita_c2=True
        ))

        groups.append(create_board_group(
            "Cama - Lateral Direita",
            (ox + L - E, oy + E, oz),
            (E, dist_y_int, H),
            material, fita_c1=True, fita_c2=True
        ))

        # 4. Estrado Superior Ventilado (Chapa de apoio bipartida)
        if has_estrado:
            larg_estrado = (L - 2 * E) / 2.0 - 2.0
            prof_estrado = dist_y_int - 4.0
            alt_estrado = 15.0

            groups.append(create_board_group(
                "Cama - Estrado Superior Esq",
                (ox + E, oy + E + 2.0, oz + H - alt_estrado),
                (larg_estrado, prof_estrado, alt_estrado),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True
            ))

            groups.append(create_board_group(
                "Cama - Estrado Superior Dir",
                (ox + (L / 2.0) + 1.0, oy + E + 2.0, oz + H - alt_estrado),
                (larg_estrado, prof_estrado, alt_estrado),
                material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True
            ))

        # 5. Gavetões Laterais Embutidos
        if num_gav > 0:
            gavs_por_lado = max(1, num_gav // 2) if lado_gavetas == "ambos" else num_gav
            comp_gaveta = (dist_y_int - (gavs_por_lado + 1) * 10.0) / float(gavs_por_lado)
            alt_gaveta = H - 60.0
            prof_gaveta = (L / 2.0) - E - 30.0

            for i in range(gavs_por_lado):
                y_pos = oy + E + 10.0 + i * (comp_gaveta + 10.0)

                # Gaveta Lado Direito
                fg_dir = create_board_group(
                    f"Cama - Frente Gaveta Dir {i+1}",
                    (ox + L - E + 2.0, y_pos, oz + 20.0),
                    (E, comp_gaveta, alt_gaveta),
                    material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True
                )
                if getattr(fg_dir, "ext", None) is None:
                    fg_dir.ext = {}
                fg_dir.ext["slide_axis"] = QVector3D(1.0, 0.0, 0.0)
                fg_dir.ext["slide_distance"] = float(prof_gaveta / 1000.0)
                groups.append(fg_dir)

                # Gaveta Lado Esquerdo
                if lado_gavetas == "ambos":
                    fg_esq = create_board_group(
                        f"Cama - Frente Gaveta Esq {i+1}",
                        (ox - 2.0, y_pos, oz + 20.0),
                        (E, comp_gaveta, alt_gaveta),
                        material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True
                    )
                    if getattr(fg_esq, "ext", None) is None:
                        fg_esq.ext = {}
                    fg_esq.ext["slide_axis"] = QVector3D(-1.0, 0.0, 0.0)
                    fg_esq.ext["slide_distance"] = float(prof_gaveta / 1000.0)
                    groups.append(fg_esq)

        return groups

    # -------------------------------------------------------------------------
    # 2. CAMA BAÚ (BASCULANTE COM PISTÕES)
    # -------------------------------------------------------------------------
    @classmethod
    def build_cama_bau(
        cls,
        largura: float = 1400.0,
        comprimento: float = 1950.0,
        altura: float = 420.0,
        espessura: float = 18.0,
        esp_fundo: float = 6.0,
        material: str = "MDF Carvalho",
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        **params: Any,
    ) -> list[Group]:
        """Cama box com baú fechado para armazenamento e tampa de estrado articulado."""
        if 'profundidade' in params and params['profundidade']:
            comprimento = float(params['profundidade'])
        if 'altura' in params and params['altura']:
            altura = float(params['altura'])
        if 'largura' in params and params['largura']:
            largura = float(params['largura'])

        E = float(espessura)
        Ef = float(esp_fundo)
        L = float(largura)
        C = float(comprimento)
        H = float(altura)
        ox, oy, oz = offset

        groups: list[Group] = []

        dist_y_int = C - 2 * E
        groups.append(create_board_group(
            "Cama Baú - Peseira",
            (ox, oy, oz),
            (L, E, H - 25.0),
            material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True
        ))

        groups.append(create_board_group(
            "Cama Baú - Cabeceira",
            (ox, oy + C - E, oz),
            (L, E, H - 25.0),
            material, fita_c1=True, fita_l1=True, fita_l2=True
        ))

        groups.append(create_board_group(
            "Cama Baú - Lateral Esq",
            (ox, oy + E, oz),
            (E, dist_y_int, H - 25.0),
            material, fita_c1=True
        ))

        groups.append(create_board_group(
            "Cama Baú - Lateral Dir",
            (ox + L - E, oy + E, oz),
            (E, dist_y_int, H - 25.0),
            material, fita_c1=True
        ))

        # Fundo interno do Baú
        groups.append(create_board_group(
            "Cama Baú - Fundo",
            (ox + E, oy + E, oz + 30.0),
            (L - 2 * E, dist_y_int, Ef),
            material
        ))

        # Divisória central longitudinal interna
        groups.append(create_board_group(
            "Cama Baú - Divisória Central",
            (ox + (L - E) / 2.0, oy + E, oz + 30.0 + Ef),
            (E, dist_y_int, H - 55.0 - Ef),
            material, fita_c1=True
        ))

        # Tampa / Estrado Articulado do Baú
        tampa = create_board_group(
            "Cama Baú - Tampa Estrado Basculante",
            (ox + 5.0, oy + 5.0, oz + H - 22.0),
            (L - 10.0, C - 10.0, 20.0),
            material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True
        )
        if getattr(tampa, "ext", None) is None:
            tampa.ext = {}
        tampa.ext["door_type"] = "basculante"
        tampa.ext["hinge_side"] = "superior"
        groups.append(tampa)

        return groups

    # -------------------------------------------------------------------------
    # 3. CAMA COM CABECEIRA INTEGRADA E MESINHAS LATERAIS
    # -------------------------------------------------------------------------
    @classmethod
    def build_cama_cabeceira(
        cls,
        largura: float = 2400.0,       # Largura total incluindo painel de cabeceira
        comprimento: float = 2050.0,   # Comprimento total (Y)
        altura: float = 1100.0,        # Altura do painel de cabeceira (Z)
        larg_cama: float = 1400.0,     # Largura do leito da cama
        alt_cama: float = 380.0,       # Altura do leito da cama
        espessura: float = 18.0,
        material: str = "MDF Carvalho",
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        **params: Any,
    ) -> list[Group]:
        """Cama plataforma integrada com painel de cabeceira estendido e mesinhas suspensas."""
        if 'profundidade' in params and params['profundidade']:
            comprimento = float(params['profundidade'])
        if 'altura' in params and params['altura']:
            altura = float(params['altura'])
        if 'largura' in params and params['largura']:
            largura = float(params['largura'])

        E = float(espessura)
        L_painel = float(largura)
        C_total = float(comprimento)
        H_painel = float(altura)
        ox, oy, oz = offset

        L_leito = float(params.get("larg_cama", min(largura * 0.65, 1400.0)))
        H_leito = float(params.get("alt_cama", 380.0))
        C_leito = C_total - E

        groups: list[Group] = []

        # 1. Painel de Cabeceira Posterior
        groups.append(create_board_group(
            "Cama - Painel de Cabeceira",
            (ox, oy + C_total - E, oz),
            (L_painel, E, H_painel),
            material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True
        ))

        # 2. Estrutura do Leito Centralizado em X
        x_leito = ox + (L_painel - L_leito) / 2.0
        comp_lat = C_leito - E

        # Peseira frontal
        groups.append(create_board_group(
            "Cama - Peseira",
            (x_leito, oy, oz),
            (L_leito, E, H_leito),
            material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True
        ))

        # Laterais do leito
        groups.append(create_board_group(
            "Cama - Lateral Esq",
            (x_leito, oy + E, oz),
            (E, comp_lat, H_leito),
            material, fita_c1=True
        ))

        groups.append(create_board_group(
            "Cama - Lateral Dir",
            (x_leito + L_leito - E, oy + E, oz),
            (E, comp_lat, H_leito),
            material, fita_c1=True
        ))

        # Longarina e Estrado
        groups.append(create_board_group(
            "Cama - Longarina Apoio",
            (x_leito + (L_leito - E) / 2.0, oy + E, oz),
            (E, comp_lat, H_leito - 20.0),
            material, fita_c1=True
        ))

        groups.append(create_board_group(
            "Cama - Estrado",
            (x_leito + E, oy + E, oz + H_leito - 18.0),
            (L_leito - 2 * E, comp_lat, 15.0),
            material, fita_c1=True, fita_c2=True
        ))

        # 3. Mesinhas de Cabeceira Suspensas Laterais
        larg_mesa = max(250.0, ((L_painel - L_leito) / 2.0) - 40.0)
        prof_mesa = 350.0
        alt_mesa = 150.0
        z_mesa = oz + H_leito * 0.75

        # Mesa Esquerda
        groups.append(create_board_group(
            "Cama - Tampo Mesinha Esq",
            (ox + 20.0, oy + C_total - E - prof_mesa, z_mesa + alt_mesa - E),
            (larg_mesa, prof_mesa, E),
            material, fita_c1=True, fita_l1=True, fita_l2=True
        ))
        groups.append(create_board_group(
            "Cama - Base Mesinha Esq",
            (ox + 20.0, oy + C_total - E - prof_mesa, z_mesa),
            (larg_mesa, prof_mesa, E),
            material, fita_c1=True, fita_l1=True, fita_l2=True
        ))

        # Mesa Direita
        x_mesa_dir = ox + L_painel - larg_mesa - 20.0
        groups.append(create_board_group(
            "Cama - Tampo Mesinha Dir",
            (x_mesa_dir, oy + C_total - E - prof_mesa, z_mesa + alt_mesa - E),
            (larg_mesa, prof_mesa, E),
            material, fita_c1=True, fita_l1=True, fita_l2=True
        ))
        groups.append(create_board_group(
            "Cama - Base Mesinha Dir",
            (x_mesa_dir, oy + C_total - E - prof_mesa, z_mesa),
            (larg_mesa, prof_mesa, E),
            material, fita_c1=True, fita_l1=True, fita_l2=True
        ))

        return groups

    # -------------------------------------------------------------------------
    # 4. BICAMA (CAMA SOLTEIRO COM CAMA AUXILIAR DESLIZANTE)
    # -------------------------------------------------------------------------
    @classmethod
    def build_bicama(
        cls,
        largura: float = 950.0,
        comprimento: float = 1950.0,
        altura: float = 500.0,
        espessura: float = 18.0,
        material: str = "MDF Carvalho",
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        **params: Any,
    ) -> list[Group]:
        """Bicama com leito superior de solteiro e cama auxiliar com rodízios deslizante."""
        if 'profundidade' in params and params['profundidade']:
            comprimento = float(params['profundidade'])
        if 'altura' in params and params['altura']:
            altura = float(params['altura'])
        if 'largura' in params and params['largura']:
            largura = float(params['largura'])

        E = float(espessura)
        L = float(largura)
        C = float(comprimento)
        H = float(altura)
        ox, oy, oz = offset

        groups: list[Group] = []

        # 1. Estrutura Cama Principal
        groups.append(create_board_group(
            "Bicama - Peseira",
            (ox, oy, oz),
            (L, E, H * 0.8),
            material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True
        ))

        groups.append(create_board_group(
            "Bicama - Cabeceira",
            (ox, oy + C - E, oz),
            (L, E, H),
            material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True
        ))

        dist_y_int = C - 2 * E
        groups.append(create_board_group(
            "Bicama - Lateral Traseira",
            (ox + L - E, oy + E, oz),
            (E, dist_y_int, H * 0.9),
            material, fita_c1=True
        ))

        alt_vao_aux = 260.0
        alt_barra_sup = H - alt_vao_aux
        groups.append(create_board_group(
            "Bicama - Barra Frontal Superior",
            (ox, oy + E, oz + alt_vao_aux),
            (E, dist_y_int, alt_barra_sup),
            material, fita_c1=True, fita_c2=True
        ))

        groups.append(create_board_group(
            "Bicama - Estrado Superior",
            (ox + E, oy + E, oz + H - 50.0),
            (L - 2 * E, dist_y_int, 15.0),
            material, fita_c1=True, fita_c2=True
        ))

        # 2. Cama Auxiliar Deslizante Inferior
        larg_aux = L - 50.0
        comp_aux = dist_y_int - 20.0
        alt_frente_aux = alt_vao_aux - 15.0

        frente_aux = create_board_group(
            "Bicama - Frente Cama Auxiliar",
            (ox - 2.0, oy + E + 10.0, oz + 10.0),
            (E, comp_aux, alt_frente_aux),
            material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True
        )
        if getattr(frente_aux, "ext", None) is None:
            frente_aux.ext = {}
        frente_aux.ext["slide_axis"] = QVector3D(-1.0, 0.0, 0.0)
        frente_aux.ext["slide_distance"] = float((larg_aux - 50.0) / 1000.0)
        groups.append(frente_aux)

        estrado_aux = create_board_group(
            "Bicama - Estrado Cama Auxiliar",
            (ox + 10.0, oy + E + 10.0 + E, oz + 45.0),
            (larg_aux, comp_aux - 2 * E, 15.0),
            material, fita_c1=True, fita_c2=True
        )
        if getattr(estrado_aux, "ext", None) is None:
            estrado_aux.ext = {}
        estrado_aux.ext["slide_axis"] = QVector3D(-1.0, 0.0, 0.0)
        estrado_aux.ext["slide_distance"] = float((larg_aux - 50.0) / 1000.0)
        groups.append(estrado_aux)

        return groups

    # -------------------------------------------------------------------------
    # 5. BELICHE PLANEJADO
    # -------------------------------------------------------------------------
    @classmethod
    def build_beliche(
        cls,
        largura: float = 950.0,
        comprimento: float = 2000.0,
        altura: float = 1600.0,
        espessura: float = 18.0,
        alt_leito_sup: float = 1200.0,
        material: str = "MDF Carvalho",
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        **params: Any,
    ) -> list[Group]:
        """Beliche planejado com 2 leitos, guarda-corpo de proteção no leito superior e escada."""
        if 'profundidade' in params and params['profundidade']:
            comprimento = float(params['profundidade'])
        if 'altura' in params and params['altura']:
            altura = float(params['altura'])
        if 'largura' in params and params['largura']:
            largura = float(params['largura'])

        E = float(espessura)
        L = float(largura)
        C = float(comprimento)
        H = float(altura)
        H_sup = float(params.get("alt_leito_sup", min(altura * 0.75, 1200.0)))
        ox, oy, oz = offset

        groups: list[Group] = []

        # 1. Peseira e Cabeceira Verticais Altas
        groups.append(create_board_group(
            "Beliche - Peseira Beliche",
            (ox, oy, oz),
            (L, E, H),
            material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True
        ))

        groups.append(create_board_group(
            "Beliche - Cabeceira Beliche",
            (ox, oy + C - E, oz),
            (L, E, H),
            material, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True
        ))

        dist_y_int = C - 2 * E
        barras_h = 140.0

        # 2. Leito Inferior
        alt_inf = 300.0
        groups.append(create_board_group(
            "Beliche - Barra Inferior Esq",
            (ox, oy + E, oz + alt_inf - barras_h),
            (E, dist_y_int, barras_h),
            material, fita_c1=True, fita_c2=True
        ))

        groups.append(create_board_group(
            "Beliche - Barra Inferior Dir",
            (ox + L - E, oy + E, oz + alt_inf - barras_h),
            (E, dist_y_int, barras_h),
            material, fita_c1=True, fita_c2=True
        ))

        groups.append(create_board_group(
            "Beliche - Estrado Inferior",
            (ox + E, oy + E, oz + alt_inf - 15.0),
            (L - 2 * E, dist_y_int, 15.0),
            material, fita_c1=True, fita_c2=True
        ))

        # 3. Leito Superior
        groups.append(create_board_group(
            "Beliche - Barra Superior Esq",
            (ox, oy + E, oz + H_sup - barras_h),
            (E, dist_y_int, barras_h),
            material, fita_c1=True, fita_c2=True
        ))

        groups.append(create_board_group(
            "Beliche - Barra Superior Dir",
            (ox + L - E, oy + E, oz + H_sup - barras_h),
            (E, dist_y_int, barras_h),
            material, fita_c1=True, fita_c2=True
        ))

        groups.append(create_board_group(
            "Beliche - Estrado Superior",
            (ox + E, oy + E, oz + H_sup - 15.0),
            (L - 2 * E, dist_y_int, 15.0),
            material, fita_c1=True, fita_c2=True
        ))

        # 4. Guarda-corpo de Proteção Superior
        alt_guardacorpo = min(350.0, H - H_sup - 50.0)
        comp_guardacorpo = dist_y_int * 0.70

        groups.append(create_board_group(
            "Beliche - Guarda-Corpo Frontal",
            (ox, oy + E, oz + H_sup),
            (E, comp_guardacorpo, alt_guardacorpo),
            material, fita_c1=True, fita_l1=True, fita_l2=True
        ))

        # 5. Escada de Acesso
        larg_escada = dist_y_int * 0.28
        y_escada = oy + E + comp_guardacorpo + 20.0

        groups.append(create_board_group(
            "Beliche - Montante Escada",
            (ox - 50.0, y_escada + larg_escada, oz),
            (E, 60.0, H_sup + 200.0),
            material, fita_c1=True, fita_l1=True, fita_l2=True
        ))

        num_degraus = 4
        espacamento_degrau = H_sup / (num_degraus + 1)
        for d in range(1, num_degraus + 1):
            groups.append(create_board_group(
                f"Beliche - Degrau {d}",
                (ox - 50.0, y_escada, oz + d * espacamento_degrau),
                (60.0, larg_escada, E),
                material, fita_c1=True, fita_c2=True
            ))

        return groups
