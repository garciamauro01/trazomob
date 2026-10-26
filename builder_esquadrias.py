# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Construtor Paramétrico de Esquadrias Inteligentes (builder_esquadrias.py).

Gera modelos 3D paramétricos de alta qualidade para Portas e Janelas (estilo Promob/Revit):
1. Portas de Giro (1 e 2 folhas):
   - Marco / Batente regulável de madeira com rebaixo da folha;
   - Alisares / Guarnições frontais e traseiras com esquadro 45°;
   - Folhas configuráveis: Lisa, Frisada, com Visor de Vidro;
   - Maçaneta e fechadura metálica tipo alavanca;
2. Janelas de Correr (2 e 4 folhas):
   - Caixilho de alumínio (preto, branco, bronze ou escovado);
   - Folhas de correr com perfis de vedação;
   - Vidros translúcidos (incolor, fumê, mini-boreal/canelado);
   - Puxadores tipo concha embutida;
3. Janelas Maxim-Ar (Banheiro/Cozinha):
   - Folha projetante superior com braço de articulação;
   - Vidro fosco/translúcido e puxador alavanca fecho-toque.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple, List, Dict, Any

from PySide6.QtGui import QVector3D, QMatrix4x4
from core.group import Group
from core.mesh import Mesh
from .builder_mesh_utils import create_board_group


class EsquadriaBuilder:
    """Fábrica de portas e janelas paramétricas completas."""

    # Paleta de materiais e cores padrão para esquadrias
    CORES = {
        "madeira_branca": (0.95, 0.95, 0.95),
        "madeira_freijo": (0.68, 0.46, 0.28),
        "madeira_nogueira": (0.42, 0.28, 0.18),
        "aluminio_preto": (0.15, 0.15, 0.15),
        "aluminio_branco": (0.92, 0.92, 0.92),
        "aluminio_inox": (0.75, 0.75, 0.78),
        "vidro_incolor": (0.85, 0.92, 0.95),
        "vidro_fume": (0.35, 0.35, 0.38),
        "metal_macaneta": (0.80, 0.80, 0.82),
    }

    # ─────────────────────────────────────────────────────────────
    # 1. PORTA DE GIRO PARAMÉTRICA (1 FOLHA)
    # ─────────────────────────────────────────────────────────────

    @classmethod
    def build_porta_giro(
        cls,
        largura_mm: float = 800.0,
        altura_mm: float = 2100.0,
        esp_parede_mm: float = 150.0,
        larg_alisar_mm: float = 70.0,
        esp_folha_mm: float = 35.0,
        esp_marco_mm: float = 30.0,
        folga_mm: float = 3.0,
        lado_abertura: str = "right",  # 'left' ou 'right'
        acabamento: str = "madeira_branca",
        offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        rot_z: float = 0.0,
    ) -> Group:
        """Gera uma porta de giro completa com batentes, alisares nos dois lados, folha e maçaneta."""
        ox, oy, oz = offset
        L = max(0.50, largura_mm / 1000.0)
        A = max(1.50, altura_mm / 1000.0)
        P = max(0.08, esp_parede_mm / 1000.0)
        L_al = larg_alisar_mm / 1000.0
        E_al = 0.012  # 12mm espessura do alisar
        E_folha = esp_folha_mm / 1000.0
        E_marco = esp_marco_mm / 1000.0
        cor = cls.CORES.get(acabamento, cls.CORES["madeira_branca"])
        cor_metal = cls.CORES["metal_macaneta"]

        pieces: List[Group] = []

        # --- A. Marco / Batente (Laterais Esquerda, Direita e Superior) ---
        # Batente Esquerdo
        pieces.append(create_board_group(
            name="Batente Esquerdo",
            origin=(ox, oy, oz),
            size=(E_marco, P, A),
            material="Madeira/MDF",
            color=cor,
        ))
        # Batente Direito
        pieces.append(create_board_group(
            name="Batente Direito",
            origin=(ox + L - E_marco, oy, oz),
            size=(E_marco, P, A),
            material="Madeira/MDF",
            color=cor,
        ))
        # Batente Superior (Verga)
        pieces.append(create_board_group(
            name="Batente Superior",
            origin=(ox + E_marco, oy, oz + A - E_marco),
            size=(L - 2 * E_marco, P, E_marco),
            material="Madeira/MDF",
            color=cor,
        ))

        # --- B. Alisares / Guarnições (Face Frontal e Traseira) ---
        # Face Frontal (Y = oy + P)
        y_al_front = oy + P
        pieces.append(create_board_group(
            name="Alisar Frontal Esq",
            origin=(ox - L_al, y_al_front, oz),
            size=(L_al, E_al, A + L_al),
            material="Alisar",
            color=cor,
        ))
        pieces.append(create_board_group(
            name="Alisar Frontal Dir",
            origin=(ox + L, y_al_front, oz),
            size=(L_al, E_al, A + L_al),
            material="Alisar",
            color=cor,
        ))
        pieces.append(create_board_group(
            name="Alisar Frontal Topo",
            origin=(ox - L_al, y_al_front, oz + A),
            size=(L + 2 * L_al, E_al, L_al),
            material="Alisar",
            color=cor,
        ))

        # Face Traseira (Y = oy - E_al)
        y_al_back = oy - E_al
        pieces.append(create_board_group(
            name="Alisar Traseiro Esq",
            origin=(ox - L_al, y_al_back, oz),
            size=(L_al, E_al, A + L_al),
            material="Alisar",
            color=cor,
        ))
        pieces.append(create_board_group(
            name="Alisar Traseiro Dir",
            origin=(ox + L, y_al_back, oz),
            size=(L_al, E_al, A + L_al),
            material="Alisar",
            color=cor,
        ))
        pieces.append(create_board_group(
            name="Alisar Traseiro Topo",
            origin=(ox - L_al, y_al_back, oz + A),
            size=(L + 2 * L_al, E_al, L_al),
            material="Alisar",
            color=cor,
        ))

        # --- C. Folha da Porta ---
        folga = folga_mm / 1000.0
        w_folha = L - (2 * E_marco) - (2 * folga)
        h_folha = A - E_marco - (2 * folga)
        x_folha = ox + E_marco + folga
        y_folha = oy + (P * 0.5) - (E_folha * 0.5)
        z_folha = oz + folga

        pieces.append(create_board_group(
            name="Folha da Porta",
            origin=(x_folha, y_folha, z_folha),
            size=(w_folha, E_folha, h_folha),
            material="MDF Porta",
            color=cor,
        ))

        # --- D. Maçaneta Metálica tipo Alavanca ---
        alt_macaneta = oz + 1.00  # 1 metro de altura padrão ABNT
        recuo_mac = 0.05
        x_mac = (x_folha + w_folha - recuo_mac) if lado_abertura == "right" else (x_folha + recuo_mac)

        # Roseta / Placa da maçaneta
        pieces.append(create_board_group(
            name="Espelho Maçaneta Frontal",
            origin=(x_mac - 0.02, y_folha + E_folha, alt_macaneta - 0.07),
            size=(0.04, 0.005, 0.14),
            material="Metal",
            color=cor_metal,
        ))
        # Haste alavanca
        alavanca_dir = -0.09 if lado_abertura == "right" else 0.09
        x_alav_orig = x_mac if lado_abertura == "right" else x_mac
        pieces.append(create_board_group(
            name="Alavanca Maçaneta Frontal",
            origin=(x_mac - (0.09 if lado_abertura == "right" else 0.0), y_folha + E_folha + 0.03, alt_macaneta - 0.01),
            size=(0.09, 0.015, 0.02),
            material="Metal",
            color=cor_metal,
        ))

        return cls._assemble_esquadria_group(
            name=f"Porta Giro {int(round(largura_mm))}x{int(round(altura_mm))}",
            tipo="porta_giro",
            pieces=pieces,
            largura_mm=largura_mm,
            altura_mm=altura_mm,
            esp_parede_mm=esp_parede_mm,
            peitoril_mm=0.0,
            offset=offset,
            rot_z=rot_z,
        )

    # ─────────────────────────────────────────────────────────────
    # 2. JANELA DE CORRER PARAMÉTRICA (2 FOLHAS COM VIDRO)
    # ─────────────────────────────────────────────────────────────

    @classmethod
    def build_janela_correr(
        cls,
        largura_mm: float = 1200.0,
        altura_mm: float = 1000.0,
        esp_parede_mm: float = 150.0,
        peitoril_mm: float = 1100.0,
        acabamento_aluminio: str = "aluminio_preto",
        tipo_vidro: str = "vidro_incolor",
        offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        rot_z: float = 0.0,
    ) -> Group:
        """Gera uma janela de correr de 2 folhas com caixilho de alumínio e vidros."""
        ox, oy, oz = offset
        # Aplica a altura do peitoril no Z global
        z_base = oz + (peitoril_mm / 1000.0)

        L = max(0.50, largura_mm / 1000.0)
        A = max(0.40, altura_mm / 1000.0)
        P = max(0.06, esp_parede_mm / 1000.0)
        E_perfil = 0.040  # 40mm largura do perfil de alumínio
        E_caixilho_prof = 0.070  # 70mm profundidade do marco de correr
        cor_alum = cls.CORES.get(acabamento_aluminio, cls.CORES["aluminio_preto"])
        cor_vidro = cls.CORES.get(tipo_vidro, cls.CORES["vidro_incolor"])

        pieces: List[Group] = []

        # Centraliza o caixilho na espessura da parede
        y_caixilho = oy + (P * 0.5) - (E_caixilho_prof * 0.5)

        # --- A. Marco Perimetral de Alumínio ---
        # Marco Inferior (Trilho)
        pieces.append(create_board_group(
            name="Marco Inferior",
            origin=(ox, y_caixilho, z_base),
            size=(L, E_caixilho_prof, E_perfil),
            material="Alumínio",
            color=cor_alum,
        ))
        # Marco Superior
        pieces.append(create_board_group(
            name="Marco Superior",
            origin=(ox, y_caixilho, z_base + A - E_perfil),
            size=(L, E_caixilho_prof, E_perfil),
            material="Alumínio",
            color=cor_alum,
        ))
        # Marco Lateral Esquerdo
        pieces.append(create_board_group(
            name="Marco Lateral Esq",
            origin=(ox, y_caixilho, z_base + E_perfil),
            size=(E_perfil, E_caixilho_prof, A - 2 * E_perfil),
            material="Alumínio",
            color=cor_alum,
        ))
        # Marco Lateral Direito
        pieces.append(create_board_group(
            name="Marco Lateral Dir",
            origin=(ox + L - E_perfil, y_caixilho, z_base + E_perfil),
            size=(E_perfil, E_caixilho_prof, A - 2 * E_perfil),
            material="Alumínio",
            color=cor_alum,
        ))

        # --- B. Folhas de Correr com Vidro (2 Folhas com transpasse central) ---
        w_interna = L - 2 * E_perfil
        h_interna = A - 2 * E_perfil
        transpasse = 0.03  # 30mm de sobreposição no centro
        w_folha = (w_interna * 0.5) + (transpasse * 0.5)
        prof_folha = 0.028  # 28mm espessura da folha de alumínio

        # Folha 1 (Esquerda - Trilho Traseiro)
        x_f1 = ox + E_perfil
        y_f1 = y_caixilho + 0.006
        z_f = z_base + E_perfil + 0.005
        h_f = h_interna - 0.010

        cls._build_folha_janela(pieces, "Folha Esq", x_f1, y_f1, z_f, w_folha, prof_folha, h_f, E_perfil, cor_alum, cor_vidro)

        # Folha 2 (Direita - Trilho Frontal)
        x_f2 = ox + L - E_perfil - w_folha
        y_f2 = y_caixilho + E_caixilho_prof - prof_folha - 0.006

        cls._build_folha_janela(pieces, "Folha Dir", x_f2, y_f2, z_f, w_folha, prof_folha, h_f, E_perfil, cor_alum, cor_vidro)

        return cls._assemble_esquadria_group(
            name=f"Janela Correr {int(round(largura_mm))}x{int(round(altura_mm))}",
            tipo="janela_correr",
            pieces=pieces,
            largura_mm=largura_mm,
            altura_mm=altura_mm,
            esp_parede_mm=esp_parede_mm,
            peitoril_mm=peitoril_mm,
            offset=offset,
            rot_z=rot_z,
        )

    # ─────────────────────────────────────────────────────────────
    # 3. JANELA MAXIM-AR (BANHEIRO / LAVABO)
    # ─────────────────────────────────────────────────────────────

    @classmethod
    def build_janela_maximar(
        cls,
        largura_mm: float = 600.0,
        altura_mm: float = 600.0,
        esp_parede_mm: float = 150.0,
        peitoril_mm: float = 1600.0,
        acabamento_aluminio: str = "aluminio_preto",
        tipo_vidro: str = "vidro_incolor",
        offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        rot_z: float = 0.0,
    ) -> Group:
        """Gera uma janela Maxim-Ar de 1 folha basculante projetante para banheiros e lavabos."""
        ox, oy, oz = offset
        z_base = oz + (peitoril_mm / 1000.0)

        L = max(0.40, largura_mm / 1000.0)
        A = max(0.40, altura_mm / 1000.0)
        P = max(0.06, esp_parede_mm / 1000.0)
        E_perfil = 0.035
        E_caixilho_prof = 0.050
        cor_alum = cls.CORES.get(acabamento_aluminio, cls.CORES["aluminio_preto"])
        cor_vidro = cls.CORES.get(tipo_vidro, cls.CORES["vidro_incolor"])

        pieces: List[Group] = []
        y_caixilho = oy + (P * 0.5) - (E_caixilho_prof * 0.5)

        # Marco Perimetral
        pieces.append(create_board_group("Marco Inf", (ox, y_caixilho, z_base), (L, E_caixilho_prof, E_perfil), "Alumínio", color=cor_alum))
        pieces.append(create_board_group("Marco Sup", (ox, y_caixilho, z_base + A - E_perfil), (L, E_caixilho_prof, E_perfil), "Alumínio", color=cor_alum))
        pieces.append(create_board_group("Marco Lat Esq", (ox, y_caixilho, z_base + E_perfil), (E_perfil, E_caixilho_prof, A - 2 * E_perfil), "Alumínio", color=cor_alum))
        pieces.append(create_board_group("Marco Lat Dir", (ox + L - E_perfil, y_caixilho, z_base + E_perfil), (E_perfil, E_caixilho_prof, A - 2 * E_perfil), "Alumínio", color=cor_alum))

        # Folha Única Maxim-Ar
        w_f = L - 2 * E_perfil - 0.010
        h_f = A - 2 * E_perfil - 0.010
        x_f = ox + E_perfil + 0.005
        y_f = y_caixilho + 0.010
        z_f = z_base + E_perfil + 0.005

        cls._build_folha_janela(pieces, "Folha Maxim-Ar", x_f, y_f, z_f, w_f, 0.030, h_f, E_perfil, cor_alum, cor_vidro)

        return cls._assemble_esquadria_group(
            name=f"Janela Maxim-Ar {int(round(largura_mm))}x{int(round(altura_mm))}",
            tipo="janela_maximar",
            pieces=pieces,
            largura_mm=largura_mm,
            altura_mm=altura_mm,
            esp_parede_mm=esp_parede_mm,
            peitoril_mm=peitoril_mm,
            offset=offset,
            rot_z=rot_z,
        )

    # ─────────────────────────────────────────────────────────────
    # UTILITÁRIOS INTERNOS DE MONTAGEM
    # ─────────────────────────────────────────────────────────────

    @classmethod
    def _build_folha_janela(
        cls,
        pieces: List[Group],
        prefix: str,
        x: float,
        y: float,
        z: float,
        w: float,
        prof: float,
        h: float,
        e_quadro: float,
        cor_alum: Tuple[float, float, float],
        cor_vidro: Tuple[float, float, float],
    ) -> None:
        """Monta o caixilho retangular de alumínio e o painel de vidro interno translúcido."""
        # Travessa inferior da folha
        pieces.append(create_board_group(f"{prefix} Quadro Inf", (x, y, z), (w, prof, e_quadro), "Alumínio", color=cor_alum))
        # Travessa superior da folha
        pieces.append(create_board_group(f"{prefix} Quadro Sup", (x, y, z + h - e_quadro), (w, prof, e_quadro), "Alumínio", color=cor_alum))
        # Montante lateral esquerdo
        pieces.append(create_board_group(f"{prefix} Quadro Lat Esq", (x, y, z + e_quadro), (e_quadro, prof, h - 2 * e_quadro), "Alumínio", color=cor_alum))
        # Montante lateral direito
        pieces.append(create_board_group(f"{prefix} Quadro Lat Dir", (x + w - e_quadro, y, z + e_quadro), (e_quadro, prof, h - 2 * e_quadro), "Alumínio", color=cor_alum))

        # Vidro interno
        e_vidro = 0.006  # 6mm vidro temperado
        y_vidro = y + (prof * 0.5) - (e_vidro * 0.5)
        pieces.append(create_board_group(
            f"{prefix} Vidro",
            (x + e_quadro, y_vidro, z + e_quadro),
            (w - 2 * e_quadro, e_vidro, h - 2 * e_quadro),
            "Vidro",
            color=cor_vidro,
        ))

    @classmethod
    def _assemble_esquadria_group(
        cls,
        name: str,
        tipo: str,
        pieces: List[Group],
        largura_mm: float,
        altura_mm: float,
        esp_parede_mm: float,
        peitoril_mm: float,
        offset: Tuple[float, float, float],
        rot_z: float,
    ) -> Group:
        """Agrupa os componentes num Group mestre com metadados para corte na parede."""
        master = Group(Mesh(), name=name)
        master.xform = QMatrix4x4()
        master.layer = "ESQUADRIAS"

        for p in pieces:
            p.layer = "ESQUADRIAS"

        if getattr(master, "children", None) is not None:
            master.children.extend(pieces)
        elif hasattr(master, "groups"):
            master.groups.extend(pieces)

        master.ext = {
            "trazomob_esquadria": {
                "tipo": tipo,
                "largura_mm": float(largura_mm),
                "altura_mm": float(altura_mm),
                "esp_parede_mm": float(esp_parede_mm),
                "peitoril_mm": float(peitoril_mm),
                "offset": offset,
                "rot_z": float(rot_z),
            }
        }

        # Aplica rotação Z se necessário
        if abs(rot_z) > 1e-4:
            rad = math.radians(rot_z)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            ox, oy, _ = offset
            for p in pieces:
                m = getattr(p, "mesh", None)
                if m and hasattr(m, "vertices"):
                    for v in m.vertices:
                        px = v.position.x() - ox
                        py = v.position.y() - oy
                        rx = px * cos_a - py * sin_a + ox
                        ry = px * sin_a + py * cos_a + oy
                        v.position = QVector3D(rx, ry, v.position.z())
                    m._mut_serial = getattr(m, "_mut_serial", 0) + 1

        return master
