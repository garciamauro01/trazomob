# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations
import math
from typing import Any
from core.group import Group
from core.mesh import Mesh
from .builder_mesh_utils import create_board_group

class ArmarioBuilder:
    """Construtor especializado para roupeiros, cabideiros, armários com prateleiras e divisórias."""

    @staticmethod
    def get_material_color(material: str) -> tuple[float, float, float]:
        from .builder import CabinetBuilder
        return CabinetBuilder.get_material_color(material)

    @staticmethod
    def _calc_desconto_traseiro_fundo(
        tipo_fundo: str = "rasgo", esp_fundo_mm: float = 6.0, recuo_fundo_mm: float = 15.0
    ) -> float:
        from .builder import CabinetBuilder
        return CabinetBuilder._calc_desconto_traseiro_fundo(tipo_fundo, esp_fundo_mm, recuo_fundo_mm)

    @staticmethod
    def build_caixa_modular(*args, **kwargs):
        from .builder import CabinetBuilder
        return CabinetBuilder.build_caixa_modular(*args, **kwargs)

    @classmethod
    def build_roupeiro_cabideiro(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        num_portas: int = 2,
        esp_mm: float = 15.0, rodape_mm: float = 100.0,
        material: str = "MDF Branco TX 15mm", material_frentes: str | None = None,
        esp_frentes_mm: float | None = None,
        tipo_fundo: str = "rasgo", esp_fundo_mm: float = 6.0,
        recuo_fundo_mm: float = 15.0, prof_rasgo_mm: float = 7.0,
        folga_fundo_mm: float = 2.0,
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        puxador_tipo: str = "alca",
        puxador_cor: str = "preto", puxador_pos: str = "padrao", desconto_perfil_mm: float = 35.0,
        perfil_modelo: str = "gola",
    ) -> list[Group]:
        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor_frente = cls.get_material_color(mat_frente)

        groups, info = cls.build_caixa_modular(
            prefixo="Roupeiro",
            largura_mm=largura_mm,
            altura_mm=altura_mm,
            prof_mm=prof_mm,
            esp_mm=esp_mm,
            rodape_mm=rodape_mm,
            tipo_topo="fechado",
            material=material,
            offset=offset,
            tem_fundo=True,
            tipo_fundo=tipo_fundo,
            esp_fundo_mm=esp_fundo_mm,
            recuo_fundo_mm=recuo_fundo_mm,
            prof_rasgo_mm=prof_rasgo_mm,
            folga_fundo_mm=folga_fundo_mm,
        )
        ox, oy, oz = info["ox"], info["oy"], info["oz"]
        L, A, P, E, R = info["L"], info["A"], info["P"], info["E"], info["R"]
        altura_caixa = info["altura_caixa"]
        largura_interna = info["largura_interna"]
        cor = info["cor"]
        desc_fundo = cls._calc_desconto_traseiro_fundo(tipo_fundo, esp_fundo_mm, recuo_fundo_mm)
        recuo_frontal_int = 0.020
        prof_int = max(0.15, P - desc_fundo - recuo_frontal_int)
        prof_div = max(0.15, P - desc_fundo)

        # Em marcenaria residencial (especialmente 3 portas):
        # 3 portas = 1 Vão Duplo (2 portas que abrem em sentido oposto com puxadores juntos no centro)
        #          + 1 Vão Simples (1 porta isolada com dobradiça na divisória).
        # Para isso é necessária 1 DIVISÓRIA ESTRUTURAL separando o vão duplo do vão simples.
        if num_portas == 3:
            larg_porta = (L - (0.003 * 4)) / 3.0
            # Vão duplo (2 portas) à esquerda e vão simples (1 porta) à direita
            larg_vao_duplo = (2.0 * larg_porta) + 0.003 - (E / 2.0)
            larg_vao_simples = largura_interna - larg_vao_duplo - E
            x_div = ox + E + larg_vao_duplo

            # 1 divisória vertical estrutural
            groups.append(create_board_group(
                "Roupeiro - Divisória Estrutural",
                (x_div, oy, oz + R + E),
                (E, prof_div, altura_caixa - 2 * E),
                material, fita_c1=True, color=cor
            ))

            z_maleiro = oz + A - E - 0.400
            z_sapateira = oz + R + E + 0.250
            z_cabide = z_maleiro - 0.060
            centro_y = oy + recuo_frontal_int + (prof_int / 2.0) - 0.012

            # Vão Duplo (lado esquerdo)
            groups.append(create_board_group(
                "Roupeiro - Maleiro Vão Duplo",
                (ox + E, oy + recuo_frontal_int, z_maleiro),
                (larg_vao_duplo, prof_int, E), material, fita_c1=True, color=cor
            ))
            groups.append(create_board_group(
                "Roupeiro - Sapateira Vão Duplo",
                (ox + E, oy + recuo_frontal_int, z_sapateira),
                (larg_vao_duplo, prof_int, E), material, fita_c1=True, color=cor
            ))
            groups.append(create_board_group(
                "Roupeiro - Varão Cabideiro Vão Duplo",
                (ox + E, centro_y, z_cabide),
                (larg_vao_duplo, 0.025, 0.015), "Alumínio Anodizado", color=(0.80, 0.82, 0.85)
            ))

            # Vão Simples (lado direito)
            x_vs = x_div + E
            groups.append(create_board_group(
                "Roupeiro - Maleiro Vão Simples",
                (x_vs, oy + recuo_frontal_int, z_maleiro),
                (larg_vao_simples, prof_int, E), material, fita_c1=True, color=cor
            ))
            groups.append(create_board_group(
                "Roupeiro - Sapateira Vão Simples",
                (x_vs, oy + recuo_frontal_int, z_sapateira),
                (larg_vao_simples, prof_int, E), material, fita_c1=True, color=cor
            ))
            groups.append(create_board_group(
                "Roupeiro - Varão Cabideiro Vão Simples",
                (x_vs, centro_y, z_cabide),
                (larg_vao_simples, 0.025, 0.015), "Alumínio Anodizado", color=(0.80, 0.82, 0.85)
            ))

            # Portas do roupeiro de 3 portas:
            # Porta 1: abre para a esquerda (dobradiça na lateral esquerda, puxador na direita -> 'left')
            # Porta 2: abre para a direita (dobradiça na divisória, puxador na esquerda -> 'right')
            # Porta 3 (isolada): abre para a direita (dobradiça na divisória, puxador na lateral direita -> 'left' ou 'single')
            alt_porta = altura_caixa - 0.006
            xp1 = ox + 0.003
            xp2 = xp1 + larg_porta + 0.003
            xp3 = xp2 + larg_porta + 0.003
            groups.append(create_board_group(
                "Roupeiro - Porta 1 (Esq Par)", (xp1, oy - E_frente, oz + R + 0.003),
                (larg_porta, E_frente, alt_porta), mat_frente,
                fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="left", is_upper=False
            ))
            groups.append(create_board_group(
                "Roupeiro - Porta 2 (Dir Par)", (xp2, oy - E_frente, oz + R + 0.003),
                (larg_porta, E_frente, alt_porta), mat_frente,
                fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="right", is_upper=False
            ))
            groups.append(create_board_group(
                "Roupeiro - Porta 3 (Isolada)", (xp3, oy - E_frente, oz + R + 0.003),
                (larg_porta, E_frente, alt_porta), mat_frente,
                fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="left", is_upper=False
            ))
            return groups

        elif num_portas >= 4:
            # Para 4 ou mais portas: divide em pares de portas (ex: 4 portas = 2 vãos duplos e 1 divisória central)
            num_divisoes = (num_portas // 2) - 1 if (num_portas % 2 == 0) else (num_portas - 1)
            if num_divisoes > 0:
                larg_vao = (largura_interna - (num_divisoes * E)) / float(num_divisoes + 1)
                for d_idx in range(num_divisoes):
                    x_div = ox + E + ((d_idx + 1) * larg_vao) + (d_idx * E)
                    groups.append(create_board_group(
                        f"Roupeiro - Divisória Estrutural {d_idx+1}",
                        (x_div, oy, oz + R + E),
                        (E, prof_div, altura_caixa - 2 * E),
                        material, fita_c1=True, color=cor
                    ))
                z_maleiro = oz + A - E - 0.400
                z_sapateira = oz + R + E + 0.250
                z_cabide = z_maleiro - 0.060
                centro_y = oy + recuo_frontal_int + (prof_int / 2.0) - 0.012
                for v_idx in range(num_divisoes + 1):
                    x_vao = ox + E + (v_idx * (larg_vao + E))
                    groups.append(create_board_group(
                        f"Roupeiro - Maleiro Vão {v_idx+1}",
                        (x_vao, oy + recuo_frontal_int, z_maleiro),
                        (larg_vao, prof_int, E), material, fita_c1=True, color=cor
                    ))
                    groups.append(create_board_group(
                        f"Roupeiro - Sapateira Vão {v_idx+1}",
                        (x_vao, oy + recuo_frontal_int, z_sapateira),
                        (larg_vao, prof_int, E), material, fita_c1=True, color=cor
                    ))
                    groups.append(create_board_group(
                        f"Roupeiro - Varão Cabideiro Vão {v_idx+1}",
                        (x_vao, centro_y, z_cabide),
                        (larg_vao, 0.025, 0.015), "Alumínio Anodizado", color=(0.80, 0.82, 0.85)
                    ))
            else:
                z_maleiro = oz + A - E - 0.400
                groups.append(create_board_group("Roupeiro - Prateleira Maleiro", (ox + E, oy + recuo_frontal_int, z_maleiro), (largura_interna, prof_int, E), material, fita_c1=True, color=cor))
                z_sapateira = oz + R + E + 0.250
                groups.append(create_board_group("Roupeiro - Prateleira Sapateira", (ox + E, oy + recuo_frontal_int, z_sapateira), (largura_interna, prof_int, E), material, fita_c1=True, color=cor))
                z_cabide = z_maleiro - 0.060
                centro_y = oy + recuo_frontal_int + (prof_int / 2.0) - 0.012
                groups.append(create_board_group("Roupeiro - Varao Cabideiro", (ox + E, centro_y, z_cabide), (largura_interna, 0.025, 0.015), "Aluminio Anodizado", color=(0.80, 0.82, 0.85)))

            alt_porta = altura_caixa - 0.006
            lp = (L - (0.003 * (num_portas + 1))) / float(num_portas)
            for i in range(num_portas):
                xp = ox + 0.003 + (i * (lp + 0.003))
                d_side = "left" if (i % 2 == 0) else "right"
                groups.append(create_board_group(
                    f"Roupeiro - Porta {i+1}",
                    (xp, oy - E_frente, oz + R + 0.003),
                    (lp, E_frente, alt_porta), mat_frente,
                    fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                    puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side=d_side, is_upper=False
                ))
            return groups
        else:
            # 1 ou 2 portas normais
            z_maleiro = oz + A - E - 0.400
            groups.append(create_board_group("Roupeiro - Prateleira Maleiro", (ox + E, oy + recuo_frontal_int, z_maleiro), (largura_interna, prof_int, E), material, fita_c1=True, color=cor))
            z_sapateira = oz + R + E + 0.250
            groups.append(create_board_group("Roupeiro - Prateleira Sapateira", (ox + E, oy + recuo_frontal_int, z_sapateira), (largura_interna, prof_int, E), material, fita_c1=True, color=cor))
            z_cabide = z_maleiro - 0.060
            centro_y = oy + recuo_frontal_int + (prof_int / 2.0) - 0.012
            groups.append(create_board_group("Roupeiro - Varao Cabideiro", (ox + E, centro_y, z_cabide), (largura_interna, 0.025, 0.015), "Aluminio Anodizado", color=(0.80, 0.82, 0.85)))

            if num_portas > 0:
                alt_porta = altura_caixa - 0.006
                if num_portas == 1:
                    groups.append(create_board_group(
                        "Roupeiro - Porta", (ox + 0.003, oy - E_frente, oz + R + 0.003),
                        (L - 0.006, E_frente, alt_porta), mat_frente,
                        fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                        puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="single", is_upper=False
                    ))
                else:
                    lp = (L - (0.003 * (num_portas + 1))) / float(num_portas)
                    groups.append(create_board_group(
                        "Roupeiro - Porta Esq", (ox + 0.003, oy - E_frente, oz + R + 0.003),
                        (lp, E_frente, alt_porta), mat_frente,
                        fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                        puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="left", is_upper=False
                    ))
                    groups.append(create_board_group(
                        "Roupeiro - Porta Dir", (ox + 0.003 + lp + 0.003, oy - E_frente, oz + R + 0.003),
                        (lp, E_frente, alt_porta), mat_frente,
                        fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                        puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="right", is_upper=False
                    ))

            return groups

    @classmethod
    def build_armario_prateleiras(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        num_portas: int = 1, num_prateleiras: int = 5,
        esp_mm: float = 15.0, rodape_mm: float = 100.0,
        material: str = "MDF Branco TX 15mm", material_frentes: str | None = None,
        esp_frentes_mm: float | None = None,
        tipo_fundo: str = "rasgo", esp_fundo_mm: float = 6.0,
        recuo_fundo_mm: float = 15.0, prof_rasgo_mm: float = 7.0,
        folga_fundo_mm: float = 2.0,
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        puxador_tipo: str = "alca",
        puxador_cor: str = "preto", puxador_pos: str = "padrao", desconto_perfil_mm: float = 35.0,
        perfil_modelo: str = "gola",
    ) -> list[Group]:
        ox, oy, oz = offset
        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor_frente = cls.get_material_color(mat_frente)

        groups, info = cls.build_caixa_modular(
            prefixo="Armário",
            largura_mm=largura_mm,
            altura_mm=altura_mm,
            prof_mm=prof_mm,
            esp_mm=esp_mm,
            rodape_mm=rodape_mm,
            tipo_topo="fechado",
            material=material,
            offset=offset,
            tem_fundo=True,
            tipo_fundo=tipo_fundo,
            esp_fundo_mm=esp_fundo_mm,
            recuo_fundo_mm=recuo_fundo_mm,
            prof_rasgo_mm=prof_rasgo_mm,
            folga_fundo_mm=folga_fundo_mm,
        )
        ox, oy, oz = info["ox"], info["oy"], info["oz"]
        L, A, P, E, R = info["L"], info["A"], info["P"], info["E"], info["R"]
        altura_caixa = info["altura_caixa"]
        largura_interna = info["largura_interna"]
        cor = info["cor"]
        desc_fundo = cls._calc_desconto_traseiro_fundo(tipo_fundo, esp_fundo_mm, recuo_fundo_mm)
        recuo_frontal_prat = 0.020
        prof_prat = max(0.10, P - desc_fundo - recuo_frontal_prat)
        prof_div = max(0.15, P - desc_fundo)

        # Em marcenaria residencial (especialmente 3 portas):
        # 3 portas = 1 Vão Duplo (2 portas abrindo em sentidos opostos com puxadores no centro)
        #          + 1 Vão Simples (1 porta isolada abrindo individualmente).
        # Para isso é necessária 1 DIVISÓRIA ESTRUTURAL separando o vão duplo do vão simples.
        if num_portas == 3:
            larg_porta = (L - (0.003 * 4)) / 3.0
            larg_vao_duplo = (2.0 * larg_porta) + 0.003 - (E / 2.0)
            larg_vao_simples = largura_interna - larg_vao_duplo - E
            x_div = ox + E + larg_vao_duplo

            # 1 divisória vertical estrutural
            groups.append(create_board_group(
                "Armário - Divisória Estrutural",
                (x_div, oy, oz + R + E),
                (E, prof_div, altura_caixa - 2 * E),
                material, fita_c1=True, color=cor
            ))

            # Prateleiras internas por vão
            if num_prateleiras > 0:
                alt_vao_util = (altura_caixa - 2 * E) - (num_prateleiras * E)
                espaco = alt_vao_util / (num_prateleiras + 1)
                for i in range(num_prateleiras):
                    z_prat = oz + R + E + espaco + (i * (espaco + E))
                    # Prateleiras no Vão Duplo
                    groups.append(create_board_group(
                        f"Armário - Prat Dupla {i+1}",
                        (ox + E, oy + recuo_frontal_prat, z_prat),
                        (larg_vao_duplo, prof_prat, E),
                        material, fita_c1=True, color=cor
                    ))
                    # Prateleiras no Vão Simples
                    x_vs = x_div + E
                    groups.append(create_board_group(
                        f"Armário - Prat Simples {i+1}",
                        (x_vs, oy + recuo_frontal_prat, z_prat),
                        (larg_vao_simples, prof_prat, E),
                        material, fita_c1=True, color=cor
                    ))

            # Portas: Par oposto (Portas 1 e 2) + Porta Isolada (Porta 3)
            alt_porta = altura_caixa - 0.006
            xp1 = ox + 0.003
            xp2 = xp1 + larg_porta + 0.003
            xp3 = xp2 + larg_porta + 0.003
            groups.append(create_board_group(
                "Armário - Porta 1 (Esq Par)", (xp1, oy - E_frente, oz + R + 0.003),
                (larg_porta, E_frente, alt_porta), mat_frente,
                fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="left", is_upper=False
            ))
            groups.append(create_board_group(
                "Armário - Porta 2 (Dir Par)", (xp2, oy - E_frente, oz + R + 0.003),
                (larg_porta, E_frente, alt_porta), mat_frente,
                fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="right", is_upper=False
            ))
            groups.append(create_board_group(
                "Armário - Porta 3 (Isolada)", (xp3, oy - E_frente, oz + R + 0.003),
                (larg_porta, E_frente, alt_porta), mat_frente,
                fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="left", is_upper=False
            ))
            return groups

        elif num_portas >= 4:
            num_divisoes = (num_portas // 2) - 1 if (num_portas % 2 == 0) else (num_portas - 1)
            if num_divisoes > 0:
                larg_vao = (largura_interna - (num_divisoes * E)) / float(num_divisoes + 1)
                for d_idx in range(num_divisoes):
                    x_div = ox + E + ((d_idx + 1) * larg_vao) + (d_idx * E)
                    groups.append(create_board_group(
                        f"Armário - Divisória Estrutural {d_idx+1}",
                        (x_div, oy, oz + R + E),
                        (E, prof_div, altura_caixa - 2 * E),
                        material, fita_c1=True, color=cor
                    ))
                if num_prateleiras > 0:
                    alt_vao_util = (altura_caixa - 2 * E) - (num_prateleiras * E)
                    espaco = alt_vao_util / (num_prateleiras + 1)
                    for v_idx in range(num_divisoes + 1):
                        x_vao = ox + E + (v_idx * (larg_vao + E))
                        for i in range(num_prateleiras):
                            z_prat = oz + R + E + espaco + (i * (espaco + E))
                            groups.append(create_board_group(
                                f"Armário - Prat Vão {v_idx+1}_{i+1}",
                                (x_vao, oy + recuo_frontal_prat, z_prat),
                                (larg_vao, prof_prat, E),
                                material, fita_c1=True, color=cor
                            ))
            else:
                if num_prateleiras > 0:
                    alt_vao_util = (altura_caixa - 2 * E) - (num_prateleiras * E)
                    espaco = alt_vao_util / (num_prateleiras + 1)
                    for i in range(num_prateleiras):
                        z_prat = oz + R + E + espaco + (i * (espaco + E))
                        groups.append(create_board_group(
                            f"Armário - Prateleira {i+1}",
                            (ox + E, oy + recuo_frontal_prat, z_prat),
                            (largura_interna, prof_prat, E),
                            material, fita_c1=True, color=cor
                        ))

            alt_porta = altura_caixa - 0.006
            lp = (L - (0.003 * (num_portas + 1))) / float(num_portas)
            for i in range(num_portas):
                xp = ox + 0.003 + (i * (lp + 0.003))
                d_side = "left" if (i % 2 == 0) else "right"
                groups.append(create_board_group(
                    f"Armário - Porta {i+1}",
                    (xp, oy - E_frente, oz + R + 0.003),
                    (lp, E_frente, alt_porta),
                    mat_frente, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                    puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side=d_side, is_upper=False
                ))
            return groups
        else:
            # 1 ou 2 portas normais
            if num_prateleiras > 0:
                alt_vao_util = (altura_caixa - 2 * E) - (num_prateleiras * E)
                espaco = alt_vao_util / (num_prateleiras + 1)
                for i in range(num_prateleiras):
                    z_prat = oz + R + E + espaco + (i * (espaco + E))
                    groups.append(create_board_group(
                        f"Armário - Prateleira {i+1}",
                        (ox + E, oy + recuo_frontal_prat, z_prat),
                        (largura_interna, prof_prat, E),
                        material, fita_c1=True, color=cor
                    ))

            if num_portas > 0:
                alt_porta = altura_caixa - 0.006
                if num_portas == 1:
                    groups.append(create_board_group(
                        "Armário - Porta",
                        (ox + 0.003, oy - E_frente, oz + R + 0.003),
                        (L - 0.006, E_frente, alt_porta),
                        mat_frente, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                        puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="single", is_upper=False
                    ))
                else:
                    lp = (L - (0.003 * (num_portas + 1))) / float(num_portas)
                    groups.append(create_board_group(
                        "Armário - Porta Esq",
                        (ox + 0.003, oy - E_frente, oz + R + 0.003),
                        (lp, E_frente, alt_porta),
                        mat_frente, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                        puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="left", is_upper=False
                    ))
                    groups.append(create_board_group(
                        "Armário - Porta Dir",
                        (ox + 0.003 + lp + 0.003, oy - E_frente, oz + R + 0.003),
                        (lp, E_frente, alt_porta),
                        mat_frente, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                        puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="right", is_upper=False
                    ))

            return groups

    @classmethod
    def build_armario_divisoria(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        num_prateleiras: int = 4, esp_mm: float = 15.0, rodape_mm: float = 100.0,
        material: str = "MDF Branco TX 15mm", material_frentes: str | None = None,
        esp_frentes_mm: float | None = None,
        tipo_fundo: str = "rasgo", esp_fundo_mm: float = 6.0,
        recuo_fundo_mm: float = 15.0, prof_rasgo_mm: float = 7.0,
        folga_fundo_mm: float = 2.0,
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        puxador_tipo: str = "alca",
        puxador_cor: str = "preto", puxador_pos: str = "padrao", desconto_perfil_mm: float = 35.0,
        perfil_modelo: str = "gola",
    ) -> list[Group]:
        ox, oy, oz = offset
        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor_frente = cls.get_material_color(mat_frente)

        groups, info = cls.build_caixa_modular(
            prefixo="Armário 2P",
            largura_mm=largura_mm,
            altura_mm=altura_mm,
            prof_mm=prof_mm,
            esp_mm=esp_mm,
            rodape_mm=rodape_mm,
            tipo_topo="fechado",
            material=material,
            offset=offset,
            tem_fundo=True,
            tipo_fundo=tipo_fundo,
            esp_fundo_mm=esp_fundo_mm,
            recuo_fundo_mm=recuo_fundo_mm,
            prof_rasgo_mm=prof_rasgo_mm,
            folga_fundo_mm=folga_fundo_mm,
        )
        ox, oy, oz = info["ox"], info["oy"], info["oz"]
        L, A, P, E, R = info["L"], info["A"], info["P"], info["E"], info["R"]
        altura_caixa = info["altura_caixa"]
        largura_interna = info["largura_interna"]
        cor = info["cor"]
        largura_vao = (largura_interna - E) / 2.0

        desc_fundo = cls._calc_desconto_traseiro_fundo(tipo_fundo, esp_fundo_mm, recuo_fundo_mm)
        prof_div = max(0.15, P - desc_fundo)
        recuo_frontal_prat = 0.020
        prof_prat = max(0.10, P - desc_fundo - recuo_frontal_prat)

        # Divisória Central
        groups.append(create_board_group("Armário 2P - Divisória Central", (ox + E + largura_vao, oy, oz + R + E), (E, prof_div, altura_caixa - 2 * E), material, fita_c1=True, color=cor))

        # Lado esquerdo: Prateleiras
        espaco_esq = (altura_caixa - 2 * E - (num_prateleiras * E)) / (num_prateleiras + 1)
        for i in range(num_prateleiras):
            z_prat = oz + R + E + espaco_esq + (i * (espaco_esq + E))
            groups.append(create_board_group(
                f"Armário - Prat Esq {i+1}",
                (ox + E, oy + recuo_frontal_prat, z_prat),
                (largura_vao, prof_prat, E),
                material, fita_c1=True, color=cor
            ))

        # Lado direito: Maleiro e Varão Cabideiro
        z_maleiro = oz + A - E - 0.400
        groups.append(create_board_group(
            "Armário - Maleiro Dir",
            (ox + E + largura_vao + E, oy + recuo_frontal_prat, z_maleiro),
            (largura_vao, prof_prat, E),
            material, fita_c1=True, color=cor
        ))
        z_cabide = z_maleiro - 0.060
        centro_y = oy + recuo_frontal_prat + (prof_prat / 2.0) - 0.012
        groups.append(create_board_group(
            "Armário - Varão Cabideiro",
            (ox + E + largura_vao + E, centro_y, z_cabide),
            (largura_vao, 0.025, 0.015),
            "Alumínio Anodizado", color=(0.80, 0.82, 0.85)
        ))

        # 2 Portas
        alt_porta = altura_caixa - 0.006
        lp = (L - 0.009) / 2.0
        groups.append(create_board_group(
            "Armário - Porta Esq", (ox + 0.003, oy - E_frente, oz + R + 0.003),
            (lp, E_frente, alt_porta), mat_frente,
            fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
            puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="left", is_upper=False
        ))
        groups.append(create_board_group(
            "Armário - Porta Dir", (ox + 0.003 + lp + 0.003, oy - E_frente, oz + R + 0.003),
            (lp, E_frente, alt_porta), mat_frente,
            fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
            puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="right", is_upper=False
        ))

        return groups

    @classmethod
    def build_armario_3portas(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        num_gavetas: int = 2, esp_mm: float = 15.0, rodape_mm: float = 100.0,
        material: str = "MDF Branco TX 15mm", material_frentes: str | None = None,
        esp_frentes_mm: float | None = None,
        tipo_fundo: str = "rasgo", esp_fundo_mm: float = 6.0,
        recuo_fundo_mm: float = 15.0, prof_rasgo_mm: float = 7.0,
        folga_fundo_mm: float = 2.0,
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        puxador_tipo: str = "alca",
        puxador_cor: str = "preto", puxador_pos: str = "padrao", desconto_perfil_mm: float = 35.0,
        perfil_modelo: str = "gola",
    ) -> list[Group]:
        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor_frente = cls.get_material_color(mat_frente)

        groups, info = cls.build_caixa_modular(
            prefixo="Armário 3P",
            largura_mm=largura_mm,
            altura_mm=altura_mm,
            prof_mm=prof_mm,
            esp_mm=esp_mm,
            rodape_mm=rodape_mm,
            tipo_topo="fechado",
            material=material,
            offset=offset,
            tem_fundo=True,
            tipo_fundo=tipo_fundo,
            esp_fundo_mm=esp_fundo_mm,
            recuo_fundo_mm=recuo_fundo_mm,
            prof_rasgo_mm=prof_rasgo_mm,
            folga_fundo_mm=folga_fundo_mm,
        )
        ox, oy, oz = info["ox"], info["oy"], info["oz"]
        L, A, P, E, R = info["L"], info["A"], info["P"], info["E"], info["R"]
        altura_caixa = info["altura_caixa"]
        largura_interna = info["largura_interna"]
        cor = info["cor"]
        largura_vao = (largura_interna - 2 * E) / 3.0

        desc_fundo = cls._calc_desconto_traseiro_fundo(tipo_fundo, esp_fundo_mm, recuo_fundo_mm)
        prof_div = max(0.15, P - desc_fundo)
        recuo_frontal_prat = 0.020
        prof_prat = max(0.10, P - desc_fundo - recuo_frontal_prat)

        # Divisórias verticais estruturais internas
        groups.append(create_board_group("Armário 3P - Divisória 1", (ox + E + largura_vao, oy, oz + R + E), (E, prof_div, altura_caixa - 2 * E), material, fita_c1=True, color=cor))
        groups.append(create_board_group("Armário 3P - Divisória 2", (ox + E + (2 * largura_vao) + E, oy, oz + R + E), (E, prof_div, altura_caixa - 2 * E), material, fita_c1=True, color=cor))

        # Maleiro superior contínuo nos 3 vãos
        z_maleiro = oz + A - E - 0.400
        for idx_v in range(3):
            xv = ox + E + (idx_v * (largura_vao + E))
            groups.append(create_board_group(
                f"Armário 3P - Maleiro Vão {idx_v+1}",
                (xv, oy + recuo_frontal_prat, z_maleiro),
                (largura_vao, prof_prat, E),
                material, fita_c1=True, color=cor
            ))

        # Vão Central: Varão Cabideiro
        z_cabide = z_maleiro - 0.060
        centro_y = oy + recuo_frontal_prat + (prof_prat / 2.0) - 0.012
        groups.append(create_board_group(
            "Armário 3P - Varão Cabideiro Centro",
            (ox + E + largura_vao + E, centro_y, z_cabide),
            (largura_vao, 0.025, 0.015),
            "Alumínio Anodizado", color=(0.80, 0.82, 0.85)
        ))

        # Vãos laterais: Prateleiras
        for v_side in (0, 2):
            xv = ox + E + (v_side * (largura_vao + E))
            for i in range(3):
                zp = oz + R + E + 0.350 + (i * 0.380)
                groups.append(create_board_group(
                    f"Armário 3P - Prat Vão {v_side+1}_{i+1}",
                    (xv, oy + recuo_frontal_prat, zp),
                    (largura_vao, prof_prat, E),
                    material, fita_c1=True, color=cor
                ))

        # 3 Portas
        alt_porta = altura_caixa - 0.006
        lp = (L - 0.012) / 3.0
        for i in range(3):
            xp = ox + 0.003 + (i * (lp + 0.003))
            d_side = "right" if i == 0 else ("left" if i == 1 else "right")
            groups.append(create_board_group(
                f"Armário 3P - Porta {i+1}",
                (xp, oy - E_frente, oz + R + 0.003),
                (lp, E_frente, alt_porta),
                mat_frente, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side=d_side, is_upper=False
            ))

        return groups

