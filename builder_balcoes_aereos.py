# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations
import math
from typing import Any
from core.group import Group
from core.mesh import Mesh
from .builder_mesh_utils import create_board_group

class BalcaoAereoBuilder:
    """Construtor especializado para balcões inferiores padrão, gaveteiros, balcões mistos, pias, aéreos e nichos."""

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

    @staticmethod
    def build_caixa_inferior(*args, **kwargs):
        from .builder import CabinetBuilder
        return CabinetBuilder.build_caixa_inferior(*args, **kwargs)

    @staticmethod
    def build_fundo_board(*args, **kwargs):
        from .builder import CabinetBuilder
        return CabinetBuilder.build_fundo_board(*args, **kwargs)

    @staticmethod
    def build_caixa_gaveta(*args, **kwargs):
        from .builder import CabinetBuilder
        return CabinetBuilder.build_caixa_gaveta(*args, **kwargs)

    @classmethod
    def build_balcao(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        esp_mm: float = 15.0, rodape_mm: float = 100.0, num_portas: int = 2,
        num_prateleiras: int = 1, tem_fundo: bool = True,
        material: str = "MDF Branco TX 15mm", material_frentes: str | None = None,
        esp_frentes_mm: float | None = None,
        tipo_fundo: str = "rasgo", esp_fundo_mm: float = 6.0,
        recuo_fundo_mm: float = 15.0, prof_rasgo_mm: float = 7.0,
        folga_fundo_mm: float = 2.0,
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        puxador_tipo: str = "alca", puxador_cor: str = "preto", puxador_pos: str = "padrao", desconto_perfil_mm: float = 35.0,
        perfil_modelo: str = "gola",
        larg_travessa_frontal_mm: float = 70.0,
        larg_travessa_traseira_mm: float = 70.0,
        travessa_frontal_em_pe: bool = False,
        travessa_traseira_em_pe: bool = False,
        recuo_porta_topo_mm: float = 50.0,
        material_travessas: str | None = None,
        esp_travessas_mm: float | None = None,
        fita_travessas_modo: str = "frontal_1L",
        fita_travessas_faces: dict[str, bool] | None = None,
        fita_caixa_modo: str = "frontal_1L",
        material_fita_caixa: str | None = None,
        material_fita_travessas: str | None = None,
        gerar_furacao: bool = True,
        dispositivo_fixacao: str = "minifix_cavilha",
    ) -> list[Group]:
        groups, info = cls.build_caixa_inferior(
            prefixo="Balcao",
            largura_mm=largura_mm, altura_mm=altura_mm, prof_mm=prof_mm,
            esp_mm=esp_mm, rodape_mm=rodape_mm, material=material, offset=offset,
            larg_travessa_frontal_mm=larg_travessa_frontal_mm,
            larg_travessa_traseira_mm=larg_travessa_traseira_mm,
            travessa_frontal_em_pe=travessa_frontal_em_pe,
            travessa_traseira_em_pe=travessa_traseira_em_pe,
            material_travessas=material_travessas,
            esp_travessas_mm=esp_travessas_mm,
            fita_travessas_modo=fita_travessas_modo,
            fita_travessas_faces=fita_travessas_faces,
            fita_caixa_modo=fita_caixa_modo,
            material_fita_caixa=material_fita_caixa,
            material_fita_travessas=material_fita_travessas,
            gerar_furacao=gerar_furacao,
            dispositivo_fixacao=dispositivo_fixacao,
        )
        ox, oy, oz = info["ox"], info["oy"], info["oz"]
        L, A, P, E, R = info["L"], info["A"], info["P"], info["E"], info["R"]
        altura_caixa, largura_interna = info["altura_caixa"], info["largura_interna"]
        cor = info["cor"]
        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor_frente = cls.get_material_color(mat_frente)

        eff_tipo_fundo = "sem_fundo" if not tem_fundo else tipo_fundo
        desc_fundo = cls._calc_desconto_traseiro_fundo(eff_tipo_fundo, esp_fundo_mm, recuo_fundo_mm)

        # Divisórias verticais estruturais
        # Regra de marcenaria: 2 portas fecham um vão inteiro livre (sem divisória central).
        # A divisória só é inserida para separar a(s) porta(s) ímpar(es) avulsa(s):
        # - 1 porta: 1 vão (sem divisória)
        # - 2 portas: 1 vão duplo (sem divisória)
        # - 3 portas: 1 divisória -> 1 vão duplo (2 portas) + 1 vão simples (1 porta)
        # - 4 portas: 1 vão (ou sem divisória)
        # - 5 portas: 1 divisória -> 2 vãos (4 portas duplas + 1 porta simples)
        num_divisoes = 1 if (num_portas % 2 == 1 and num_portas >= 3) else 0

        prof_div = max(0.15, P - desc_fundo)
        alt_div = (altura_caixa - E) if (travessa_frontal_em_pe and travessa_traseira_em_pe) else (altura_caixa - 2 * E)
        recuo_frontal_prat = 0.025
        prof_prat = max(0.10, P - desc_fundo - recuo_frontal_prat)

        largura_vaos = []
        x_vaos = []

        if num_divisoes == 1:
            # Para 3 portas: Vão Duplo (2 portas juntas) + Vão Simples (1 porta isolada)
            # A largura de cada porta é proporcional: o vão de 2 portas tem o dobro da largura da porta avulsa
            larg_base_porta = (largura_interna - E) / num_portas
            # Vão das 2 portas (duplo) à esquerda e porta avulsa à direita
            larg_vao_duplo = 2.0 * larg_base_porta
            larg_vao_simples = larg_base_porta

            x_div = ox + E + larg_vao_duplo
            groups.append(create_board_group(
                "Balcao - Divisoria Central",
                (x_div, oy, oz + R + E),
                (E, prof_div, alt_div),
                material, fita_c1=True, color=cor
            ))

            # Vão 1 (2 portas) e Vão 2 (1 porta)
            largura_vaos = [larg_vao_duplo, larg_vao_simples]
            x_vaos = [ox + E, x_div + E]

            # Prateleiras internas por vão
            if num_prateleiras > 0:
                espaco_util = altura_caixa - 2 * E
                passo = espaco_util / (num_prateleiras + 1)
                for v_idx, (xv, lv) in enumerate(zip(x_vaos, largura_vaos)):
                    nome_vao = "Vao 2P" if v_idx == 0 else "Vao 1P"
                    for i in range(1, num_prateleiras + 1):
                        z_prat = oz + R + E + (i * passo)
                        groups.append(create_board_group(
                            f"Balcao - {nome_vao} Prateleira {i}",
                            (xv, oy + recuo_frontal_prat, z_prat),
                            (lv - 0.002, prof_prat, E),
                            material, fita_c1=True, color=cor
                        ))
        else:
            # Vão único contínuo (portas pares como 2 ou 4 portas, ou porta única)
            largura_vaos.append(largura_interna)
            x_vaos.append(ox + E)
            if num_prateleiras > 0:
                espaco_util = altura_caixa - 2 * E
                passo = espaco_util / (num_prateleiras + 1)
                for i in range(1, num_prateleiras + 1):
                    z_prat = oz + R + E + (i * passo)
                    groups.append(create_board_group(
                        f"Balcao - Prateleira {i}",
                        (ox + E, oy + recuo_frontal_prat, z_prat),
                        (largura_interna - 0.002, prof_prat, E),
                        material, fita_c1=True, color=cor
                    ))

        fundo_grp = cls.build_fundo_board(
            prefixo="Balcao",
            largura_interna_m=largura_interna,
            altura_interna_m=altura_caixa - 2 * E,
            largura_total_m=L,
            altura_total_caixa_m=altura_caixa,
            prof_total_m=P,
            esp_lateral_m=E,
            origin_caixa=(ox, oy, oz + R),
            z_interno_base_m=oz + R + E,
            tipo_fundo=eff_tipo_fundo,
            esp_fundo_mm=esp_fundo_mm,
            recuo_fundo_mm=recuo_fundo_mm,
            prof_rasgo_mm=prof_rasgo_mm,
            folga_fundo_mm=folga_fundo_mm,
        )
        if fundo_grp:
            groups.append(fundo_grp)

        if num_portas > 0:
            recuo_topo = (recuo_porta_topo_mm / 1000.0) if travessa_frontal_em_pe else 0.0
            alt_porta = max(0.05, altura_caixa - recuo_topo - 0.006)
            alt_porta_mm = alt_porta * 1000.0

            from .machining import make_hinge_cup_holes
            ops_porta = [o.to_dict() for o in make_hinge_cup_holes(alt_porta_mm)] if gerar_furacao else []

            # Largura de cada porta dividida uniformemente pelo vão total da frente
            folga_entre_portas = 0.003
            larg_total_disponivel = L - 0.006 - (num_portas - 1) * folga_entre_portas
            larg_porta = max(0.10, larg_total_disponivel / num_portas)

            x_porta = ox + 0.003
            for p_i in range(num_portas):
                if num_portas == 1:
                    d_side = "single"
                    p_nome = "Balcao - Porta Unica"
                elif num_portas == 2:
                    d_side = "left" if p_i == 0 else "right"
                    p_nome = f"Balcao - Porta {'Esq' if p_i == 0 else 'Dir'}"
                else:
                    d_side = "left" if (p_i % 2 == 0) else "right"
                    lado_txt = "Esq" if d_side == "left" else "Dir"
                    p_nome = f"Balcao - Porta {p_i+1} ({lado_txt})"

                groups.append(create_board_group(
                    p_nome,
                    (x_porta, oy - E_frente, oz + R + 0.003),
                    (larg_porta, E_frente, alt_porta),
                    mat_frente,
                    fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                    puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos,
                    desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                    door_side=d_side, is_upper=False,
                    operacoes=ops_porta,
                ))
                x_porta += larg_porta + folga_entre_portas

        return groups

    @classmethod
    def build_gaveteiro(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        num_gavetas: int = 4, esp_mm: float = 15.0, rodape_mm: float = 100.0,
        material: str = "MDF Branco TX 15mm", material_frentes: str | None = None,
        esp_frentes_mm: float | None = None,
        tipo_fundo: str = "rasgo", esp_fundo_mm: float = 6.0,
        recuo_fundo_mm: float = 15.0, prof_rasgo_mm: float = 7.0,
        folga_fundo_mm: float = 2.0,
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        puxador_tipo: str = "alca", puxador_cor: str = "preto", puxador_pos: str = "padrao", desconto_perfil_mm: float = 35.0,
        perfil_modelo: str = "gola",
        larg_travessa_frontal_mm: float = 70.0,
        larg_travessa_traseira_mm: float = 70.0,
        travessa_frontal_em_pe: bool = False,
        travessa_traseira_em_pe: bool = False,
        recuo_porta_topo_mm: float = 50.0,
        material_travessas: str | None = None,
        esp_travessas_mm: float | None = None,
        fita_travessas_modo: str = "frontal_1L",
        fita_travessas_faces: dict[str, bool] | None = None,
        fita_caixa_modo: str = "frontal_1L",
        material_fita_caixa: str | None = None,
        material_fita_travessas: str | None = None,
        tipo_fundo_gaveta: str = "rasgo",
        folga_corredica_mm: float = 26.0,
        material_gaveta: str | None = None,
        esp_gaveta_mm: float = 15.0,
        material_fita_gaveta: str | None = None,
        material_fundo_gaveta: str | None = None,
        esp_fundo_gaveta_mm: float = 6.0,
        gerar_furacao: bool = True,
        dispositivo_fixacao: str = "minifix_cavilha",
    ) -> list[Group]:
        groups, info = cls.build_caixa_inferior(
            prefixo="Gaveteiro",
            largura_mm=largura_mm, altura_mm=altura_mm, prof_mm=prof_mm,
            esp_mm=esp_mm, rodape_mm=rodape_mm, material=material, offset=offset,
            larg_travessa_frontal_mm=larg_travessa_frontal_mm,
            larg_travessa_traseira_mm=larg_travessa_traseira_mm,
            travessa_frontal_em_pe=travessa_frontal_em_pe,
            travessa_traseira_em_pe=travessa_traseira_em_pe,
            material_travessas=material_travessas,
            esp_travessas_mm=esp_travessas_mm,
            fita_travessas_modo=fita_travessas_modo,
            fita_travessas_faces=fita_travessas_faces,
            fita_caixa_modo=fita_caixa_modo,
            material_fita_caixa=material_fita_caixa,
            material_fita_travessas=material_fita_travessas,
            gerar_furacao=gerar_furacao,
            dispositivo_fixacao=dispositivo_fixacao,
        )
        ox, oy, oz = info["ox"], info["oy"], info["oz"]
        L, A, P, E, R = info["L"], info["A"], info["P"], info["E"], info["R"]
        altura_caixa, largura_interna = info["altura_caixa"], info["largura_interna"]
        cor = info["cor"]
        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor_frente = cls.get_material_color(mat_frente)

        fundo_grp = cls.build_fundo_board(
            prefixo="Gaveteiro",
            largura_interna_m=largura_interna,
            altura_interna_m=altura_caixa - 2 * E,
            largura_total_m=L,
            altura_total_caixa_m=altura_caixa,
            prof_total_m=P,
            esp_lateral_m=E,
            origin_caixa=(ox, oy, oz + R),
            z_interno_base_m=oz + R + E,
            tipo_fundo=tipo_fundo,
            esp_fundo_mm=esp_fundo_mm,
            recuo_fundo_mm=recuo_fundo_mm,
            prof_rasgo_mm=prof_rasgo_mm,
            folga_fundo_mm=folga_fundo_mm,
        )
        if fundo_grp:
            groups.append(fundo_grp)

        desc_fundo = cls._calc_desconto_traseiro_fundo(tipo_fundo, esp_fundo_mm, recuo_fundo_mm)
        num_gav = max(1, num_gavetas)
        recuo_topo = (recuo_porta_topo_mm / 1000.0) if travessa_frontal_em_pe else 0.0
        alt_disponivel_frentes = max(0.10, altura_caixa - recuo_topo)
        alt_frente = (alt_disponivel_frentes - (num_gav + 1) * 0.003) / num_gav
        larg_frente = L - 0.006
        prof_gaveta = max(0.15, min(P - 0.050, P - desc_fundo - 0.015))

        larg_corredica = max(0.010, float(folga_corredica_mm) / 1000.0)
        larg_caixa_gav = max(0.08, largura_interna - larg_corredica)
        alt_caixa_gav = max(0.06, alt_frente - 0.040)

        # Materiais da gaveta
        mat_gav = material_gaveta or material
        mat_fg = material_fundo_gaveta or f"MDF Fundo {int(esp_fundo_gaveta_mm)}mm"

        for i in range(num_gav):
            z_frente = oz + R + 0.003 + (i * (alt_frente + 0.003))
            groups.append(create_board_group(
                f"Gaveteiro - Frente {i+1}", (ox + 0.003, oy - E_frente, z_frente),
                (larg_frente, E_frente, alt_frente), mat_frente, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="drawer", is_upper=False
            ))

            z_caixa = z_frente + 0.015
            x_caixa = ox + E + (larg_corredica / 2.0)
            y_caixa = oy + 0.010

            gav_pieces = cls.build_caixa_gaveta(
                prefixo=f"Gaveta {i+1}",
                x_caixa=x_caixa,
                y_caixa=y_caixa,
                z_caixa=z_caixa,
                larg_caixa=larg_caixa_gav,
                prof_caixa=prof_gaveta,
                alt_caixa=alt_caixa_gav,
                material_gaveta=mat_gav,
                esp_gaveta_mm=esp_gaveta_mm,
                material_fita_gaveta=material_fita_gaveta,
                tipo_fundo_gaveta=tipo_fundo_gaveta,
                material_fundo_gaveta=mat_fg,
                esp_fundo_gaveta_mm=esp_fundo_gaveta_mm,
            )
            groups.extend(gav_pieces)

        return groups

    @classmethod
    def build_balcao_misto(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        num_gavetas: int = 4, largura_gaveteiro_mm: float = 450.0,
        num_portas: int = 2, num_prateleiras: int = 1,
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
        larg_travessa_frontal_mm: float = 70.0,
        larg_travessa_traseira_mm: float = 70.0,
        travessa_frontal_em_pe: bool = False,
        travessa_traseira_em_pe: bool = False,
        recuo_porta_topo_mm: float = 50.0,
        material_travessas: str | None = None,
        esp_travessas_mm: float | None = None,
        fita_travessas_modo: str = "frontal_1L",
        fita_travessas_faces: dict[str, bool] | None = None,
        fita_caixa_modo: str = "frontal_1L",
        material_fita_caixa: str | None = None,
        material_fita_travessas: str | None = None,
        tipo_fundo_gaveta: str = "rasgo",
        folga_corredica_mm: float = 26.0,
        material_gaveta: str | None = None,
        esp_gaveta_mm: float = 15.0,
        material_fita_gaveta: str | None = None,
        material_fundo_gaveta: str | None = None,
        esp_fundo_gaveta_mm: float = 6.0,
        gerar_furacao: bool = True,
        dispositivo_fixacao: str = "minifix_cavilha",
    ) -> list[Group]:
        """Gera Balcão Misto (Gaveteiro 4 gavetas à esquerda + 2 portas à direita com divisória)."""
        # Constrói a caixa básica externa (laterais, base e rodapé)
        groups, info = cls.build_caixa_inferior(
            prefixo="Balcao Misto",
            largura_mm=largura_mm, altura_mm=altura_mm, prof_mm=prof_mm,
            esp_mm=esp_mm, rodape_mm=rodape_mm, material=material, offset=offset,
            larg_travessa_frontal_mm=larg_travessa_frontal_mm,
            larg_travessa_traseira_mm=larg_travessa_traseira_mm,
            travessa_frontal_em_pe=travessa_frontal_em_pe,
            travessa_traseira_em_pe=travessa_traseira_em_pe,
            material_travessas=material_travessas,
            esp_travessas_mm=esp_travessas_mm,
            fita_travessas_modo=fita_travessas_modo,
            fita_travessas_faces=fita_travessas_faces,
            fita_caixa_modo=fita_caixa_modo,
            material_fita_caixa=material_fita_caixa,
            material_fita_travessas=material_fita_travessas,
            gerar_furacao=gerar_furacao,
            dispositivo_fixacao=dispositivo_fixacao,
        )
        ox, oy, oz = info["ox"], info["oy"], info["oz"]
        L, A, P, E, R = info["L"], info["A"], info["P"], info["E"], info["R"]
        altura_caixa, largura_interna = info["altura_caixa"], info["largura_interna"]
        cor = info["cor"]
        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor_frente = cls.get_material_color(mat_frente)
        LTF = info["LTF"]
        LTT = info["LTT"]

        # Largura do vão do gaveteiro (m)
        L_gav = min(max(0.30, largura_gaveteiro_mm / 1000.0), largura_interna - 0.40)
        # Largura do vão das portas (m)
        L_portas = max(0.20, largura_interna - L_gav - E)

        eff_tipo_fundo = tipo_fundo
        desc_fundo = cls._calc_desconto_traseiro_fundo(eff_tipo_fundo, esp_fundo_mm, recuo_fundo_mm)

        # Divisória vertical intermediária (apoiada na base)
        # Se a travessa frontal ou traseira for deitada (horizontal no topo, ocupando E no z do topo),
        # a divisória fica entre a base e as travessas: altura_caixa - 2 * E
        # Se ambas forem em pé, a divisória vai até o topo da caixa: altura_caixa - E
        prof_divisoria = max(0.15, P - desc_fundo)
        if (not travessa_frontal_em_pe) or (not travessa_traseira_em_pe):
            alt_divisoria = altura_caixa - 2 * E
        else:
            alt_divisoria = altura_caixa - E
        x_div = ox + E + L_gav
        groups.append(create_board_group("Balcao Misto - Divisoria", (x_div, oy, oz + R + E), (E, prof_divisoria, alt_divisoria), material, fita_c1=True, color=cor))
        x_portas_interno = x_div + E

        # Fundo do armário
        fundo_grp = cls.build_fundo_board(
            prefixo="Balcao Misto",
            largura_interna_m=largura_interna,
            altura_interna_m=altura_caixa - 2 * E,
            largura_total_m=L,
            altura_total_caixa_m=altura_caixa,
            prof_total_m=P,
            esp_lateral_m=E,
            origin_caixa=(ox, oy, oz + R),
            z_interno_base_m=oz + R + E,
            tipo_fundo=eff_tipo_fundo,
            esp_fundo_mm=esp_fundo_mm,
            recuo_fundo_mm=recuo_fundo_mm,
            prof_rasgo_mm=prof_rasgo_mm,
            folga_fundo_mm=folga_fundo_mm,
        )
        if fundo_grp:
            groups.append(fundo_grp)

        # Prateleira no vão das portas (direita)
        if num_prateleiras > 0:
            espaco_util = altura_caixa - 2 * E
            passo = espaco_util / (num_prateleiras + 1)
            recuo_frontal_prat = 0.025
            prof_prat = max(0.10, P - desc_fundo - recuo_frontal_prat)
            for i in range(1, num_prateleiras + 1):
                z_prat = oz + R + E + (i * passo)
                groups.append(create_board_group(
                    f"Balcao Misto - Prateleira {i}", (x_portas_interno, oy + recuo_frontal_prat, z_prat),
                    (L_portas - 0.002, prof_prat, E), material, fita_c1=True, color=cor
                ))

        recuo_topo = (recuo_porta_topo_mm / 1000.0) if travessa_frontal_em_pe else 0.0

        # Gaveteiro (esquerda)
        num_gav = max(1, num_gavetas)
        alt_disponivel_gav = max(0.10, altura_caixa - recuo_topo)
        alt_frente = (alt_disponivel_gav - (num_gav + 1) * 0.003) / num_gav
        larg_frente = L_gav + E + (E / 2.0) - 0.006
        prof_gaveta = max(0.15, min(P - 0.050, P - desc_fundo - 0.015))
        larg_corredica = max(0.010, float(folga_corredica_mm) / 1000.0)
        larg_caixa_gav = max(0.08, L_gav - larg_corredica)
        alt_caixa_gav = max(0.06, alt_frente - 0.040)
        x_frente = ox + 0.003

        # Materiais da gaveta
        mat_gav = material_gaveta or material
        mat_fg = material_fundo_gaveta or f"MDF Fundo {int(esp_fundo_gaveta_mm)}mm"

        for i in range(num_gav):
            z_frente = oz + R + 0.003 + (i * (alt_frente + 0.003))
            groups.append(create_board_group(
                f"Gaveteiro - Frente {i+1}", (x_frente, oy - E_frente, z_frente),
                (larg_frente, E_frente, alt_frente), mat_frente, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="drawer", is_upper=False
            ))

            z_caixa = z_frente + 0.015
            x_caixa = ox + E + (larg_corredica / 2.0)
            y_caixa = oy + 0.010

            gav_pieces = cls.build_caixa_gaveta(
                prefixo=f"Gaveta {i+1}",
                x_caixa=x_caixa,
                y_caixa=y_caixa,
                z_caixa=z_caixa,
                larg_caixa=larg_caixa_gav,
                prof_caixa=prof_gaveta,
                alt_caixa=alt_caixa_gav,
                material_gaveta=mat_gav,
                esp_gaveta_mm=esp_gaveta_mm,
                material_fita_gaveta=material_fita_gaveta,
                tipo_fundo_gaveta=tipo_fundo_gaveta,
                material_fundo_gaveta=mat_fg,
                esp_fundo_gaveta_mm=esp_fundo_gaveta_mm,
            )
            groups.extend(gav_pieces)

        # Portas (direita)
        alt_porta = max(0.05, altura_caixa - recuo_topo - 0.006)
        larg_total_portas = L_portas + (E / 2.0) + E - 0.006
        x_inicio_portas = x_div + (E / 2.0) + 0.0015
        num_p = max(1, num_portas)

        if num_p == 1:
            groups.append(create_board_group(
                "Balcao Misto - Porta Unica", (x_inicio_portas, oy - E_frente, oz + R + 0.003),
                (larg_total_portas, E_frente, alt_porta), mat_frente, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="single", is_upper=False
            ))
        else:
            larg_cada_porta = (larg_total_portas - 0.003) / 2.0
            groups.append(create_board_group(
                "Balcao Misto - Porta Esq", (x_inicio_portas, oy - E_frente, oz + R + 0.003),
                (larg_cada_porta, E_frente, alt_porta), mat_frente, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="left", is_upper=False
            ))
            groups.append(create_board_group(
                "Balcao Misto - Porta Dir", (x_inicio_portas + larg_cada_porta + 0.003, oy - E_frente, oz + R + 0.003),
                (larg_cada_porta, E_frente, alt_porta), mat_frente, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="right", is_upper=False
            ))

        return groups

    @classmethod
    def build_aereo(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        esp_mm: float = 15.0, num_portas: int = 2, num_prateleiras: int = 1,
        material: str = "MDF Branco TX 15mm", material_frentes: str | None = None,
        esp_frentes_mm: float | None = None,
        tipo_fundo: str = "rasgo", esp_fundo_mm: float = 6.0,
        recuo_fundo_mm: float = 15.0, prof_rasgo_mm: float = 7.0,
        folga_fundo_mm: float = 2.0,
        offset: tuple[float, float, float] = (0.0, 0.0, 1.4),
        puxador_tipo: str = "alca",
        puxador_cor: str = "preto", puxador_pos: str = "padrao", desconto_perfil_mm: float = 35.0,
        perfil_modelo: str = "gola",
    ) -> list[Group]:
        ox, oy, oz = offset
        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor_frente = cls.get_material_color(mat_frente)

        groups, info = cls.build_caixa_modular(
            prefixo="Aereo",
            largura_mm=largura_mm,
            altura_mm=altura_mm,
            prof_mm=prof_mm,
            esp_mm=esp_mm,
            rodape_mm=0.0,
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
        L, A, P, E = info["L"], info["A"], info["P"], info["E"]
        largura_interna = info["largura_interna"]
        cor = info["cor"]
        desc_fundo = cls._calc_desconto_traseiro_fundo(tipo_fundo, esp_fundo_mm, recuo_fundo_mm)

        if num_prateleiras > 0:
            espaco_util = A - 2 * E
            passo = espaco_util / (num_prateleiras + 1)
            recuo_frontal_prat = 0.020
            prof_prat = max(0.10, P - desc_fundo - recuo_frontal_prat)
            for i in range(1, num_prateleiras + 1):
                z_prat = oz + E + (i * passo)
                groups.append(create_board_group(
                    f"Aereo - Prateleira {i}", (ox + E, oy + recuo_frontal_prat, z_prat),
                    (largura_interna - 0.002, prof_prat, E), material, fita_c1=True, color=cor
                ))

        if num_portas > 0:
            alt_porta = max(0.05, A - 0.006)
            alt_porta_mm = alt_porta * 1000.0

            from .machining import make_hinge_cup_holes
            ops_porta = [o.to_dict() for o in make_hinge_cup_holes(alt_porta_mm)]

            # Largura de cada porta dividida uniformemente pelo vão total da frente
            folga_entre_portas = 0.003
            larg_total_disponivel = L - 0.006 - (num_portas - 1) * folga_entre_portas
            larg_porta = max(0.10, larg_total_disponivel / num_portas)

            x_porta = ox + 0.003
            for p_i in range(num_portas):
                if num_portas == 1:
                    d_side = "single"
                    p_nome = "Aereo - Porta Unica"
                elif num_portas == 2:
                    d_side = "left" if p_i == 0 else "right"
                    p_nome = f"Aereo - Porta {'Esq' if p_i == 0 else 'Dir'}"
                else:
                    d_side = "left" if (p_i % 2 == 0) else "right"
                    lado_txt = "Esq" if d_side == "left" else "Dir"
                    p_nome = f"Aereo - Porta {p_i+1} ({lado_txt})"

                groups.append(create_board_group(
                    p_nome,
                    (x_porta, oy - E_frente, oz + 0.003),
                    (larg_porta, E_frente, alt_porta),
                    mat_frente,
                    fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                    color=cor_frente,
                    puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos,
                    desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                    door_side=d_side, is_upper=True,
                    operacoes=ops_porta,
                ))
                x_porta += larg_porta + folga_entre_portas

        return groups

    @classmethod
    def build_nicho(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        esp_mm: float = 15.0, divisoes_vert: int = 0, divisoes_horiz: int = 1,
        material: str = "MDF Louro Freijó 15mm", offset: tuple[float, float, float] = (0.0, 0.0, 1.4)
    ) -> list[Group]:
        groups, info = cls.build_caixa_modular(
            prefixo="Nicho",
            largura_mm=largura_mm,
            altura_mm=altura_mm,
            prof_mm=prof_mm,
            esp_mm=esp_mm,
            rodape_mm=0.0,
            tipo_topo="fechado",
            material=material,
            offset=offset,
            tem_fundo=False,
        )
        ox, oy, oz = info["ox"], info["oy"], info["oz"]
        L, A, P, E = info["L"], info["A"], info["P"], info["E"]
        largura_interna = info["largura_interna"]
        altura_interna = A - 2 * E
        cor = info["cor"]

        if divisoes_horiz > 0:
            passo = (altura_interna - (divisoes_horiz * E)) / (divisoes_horiz + 1)
            for i in range(1, divisoes_horiz + 1):
                z_div = oz + E + (i * passo) + ((i - 1) * E)
                groups.append(create_board_group(
                    f"Nicho - Divisao Horiz {i}", (ox + E, oy, z_div),
                    (largura_interna, P, E), material, fita_c1=True, color=cor
                ))

        if divisoes_vert > 0:
            passo_v = (largura_interna - (divisoes_vert * E)) / (divisoes_vert + 1)
            for i in range(1, divisoes_vert + 1):
                x_div = ox + E + (i * passo_v) + ((i - 1) * E)
                groups.append(create_board_group(
                    f"Nicho - Divisao Vert {i}", (x_div, oy, oz + E),
                    (E, P, altura_interna), material, fita_c1=True, color=cor
                ))

        return groups

    @classmethod
    def build_balcao_pia(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        esp_mm: float = 15.0, rodape_mm: float = 100.0, num_portas: int = 2,
        material: str = "MDF Branco TX 15mm", material_frentes: str | None = None,
        esp_frentes_mm: float | None = None,
        tem_fundo: bool = False,
        tipo_fundo: str = "sem_fundo", esp_fundo_mm: float = 6.0,
        recuo_fundo_mm: float = 15.0, prof_rasgo_mm: float = 7.0,
        folga_fundo_mm: float = 2.0,
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        puxador_tipo: str = "alca",
        puxador_cor: str = "preto", puxador_pos: str = "padrao", desconto_perfil_mm: float = 35.0,
        perfil_modelo: str = "gola",
        # Parâmetros das travessas (unificados e compatibilidade)
        travessa_frontal_em_pe: bool = True,
        travessa_traseira_em_pe: bool = False,
        larg_travessa_frontal_mm: float = 70.0,
        larg_travessa_traseira_mm: float = 70.0,
        recuo_porta_topo_mm: float = 50.0,
        larg_travessa_mm: float | None = None,
        recuo_porta_pia_mm: float | None = None,
        material_travessas: str | None = None,
        esp_travessas_mm: float | None = None,
        fita_travessas_modo: str = "frontal_1L",
        fita_travessas_faces: dict[str, bool] | None = None,
        fita_caixa_modo: str = "frontal_1L",
        material_fita_caixa: str | None = None,
        material_fita_travessas: str | None = None,
        gerar_furacao: bool = True,
        dispositivo_fixacao: str = "minifix_cavilha",
    ) -> list[Group]:
        """Balcão de pia/cuba."""
        if larg_travessa_mm is not None:
            larg_travessa_frontal_mm = larg_travessa_mm
        if recuo_porta_pia_mm is not None:
            recuo_porta_topo_mm = recuo_porta_pia_mm

        groups, info = cls.build_caixa_inferior(
            prefixo="Balcao Pia",
            largura_mm=largura_mm, altura_mm=altura_mm, prof_mm=prof_mm,
            esp_mm=esp_mm, rodape_mm=rodape_mm, material=material, offset=offset,
            larg_travessa_frontal_mm=larg_travessa_frontal_mm,
            larg_travessa_traseira_mm=larg_travessa_traseira_mm,
            travessa_frontal_em_pe=travessa_frontal_em_pe,
            travessa_traseira_em_pe=travessa_traseira_em_pe,
            material_travessas=material_travessas,
            esp_travessas_mm=esp_travessas_mm,
            fita_travessas_modo=fita_travessas_modo,
            fita_travessas_faces=fita_travessas_faces,
            fita_caixa_modo=fita_caixa_modo,
            material_fita_caixa=material_fita_caixa,
            material_fita_travessas=material_fita_travessas,
            gerar_furacao=gerar_furacao,
            dispositivo_fixacao=dispositivo_fixacao,
        )
        ox, oy, oz = info["ox"], info["oy"], info["oz"]
        L, A, P, E, R = info["L"], info["A"], info["P"], info["E"], info["R"]
        altura_caixa, largura_interna = info["altura_caixa"], info["largura_interna"]
        cor = info["cor"]
        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor_frente = cls.get_material_color(mat_frente)

        # Fundo (opcional — normalmente sem fundo no balcão de pia por causa do sifão)
        eff_tipo_fundo = "sem_fundo" if not tem_fundo else tipo_fundo
        fundo_grp = cls.build_fundo_board(
            prefixo="Balcao Pia",
            largura_interna_m=largura_interna,
            altura_interna_m=altura_caixa - 2 * E,
            largura_total_m=L,
            altura_total_caixa_m=altura_caixa,
            prof_total_m=P,
            esp_lateral_m=E,
            origin_caixa=(ox, oy, oz + R),
            z_interno_base_m=oz + R + E,
            tipo_fundo=eff_tipo_fundo,
            esp_fundo_mm=esp_fundo_mm,
            recuo_fundo_mm=recuo_fundo_mm,
            prof_rasgo_mm=prof_rasgo_mm,
            folga_fundo_mm=folga_fundo_mm,
        )
        if fundo_grp:
            groups.append(fundo_grp)

        # Portas — quando a travessa frontal está em pé, o topo das portas fica rebaixado (recuo vertical)
        if num_portas > 0:
            recuo_topo = (recuo_porta_topo_mm / 1000.0) if travessa_frontal_em_pe else 0.0
            alt_porta = max(0.05, altura_caixa - recuo_topo - 0.003)
            porta_z0 = oz + R + 0.003

            if num_portas == 1:
                larg_porta = L - 0.006
                groups.append(create_board_group(
                    "Balcao Pia - Porta Unica",
                    (ox + 0.003, oy - E_frente, porta_z0),
                    (larg_porta, E_frente, alt_porta), mat_frente,
                    fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                    puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos,
                    desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                    door_side="single", is_upper=False
                ))
            else:
                larg_porta = (L - 0.009) / num_portas
                for i in range(num_portas):
                    side = "left" if i == 0 else ("right" if i == num_portas - 1 else "center")
                    groups.append(create_board_group(
                        f"Balcao Pia - Porta {i + 1}",
                        (ox + 0.003 + i * (larg_porta + 0.003), oy - E_frente, porta_z0),
                        (larg_porta, E_frente, alt_porta), mat_frente,
                        fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                        puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos,
                        desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                        door_side=side, is_upper=False
                    ))

        return groups


    @classmethod
    def build_gabinete_banheiro(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        esp_mm: float = 15.0, material: str = "MDF Branco TX 15mm",
        material_frentes: str | None = None, esp_frentes_mm: float | None = None,
        tipo_fundo: str = "rasgo", esp_fundo_mm: float = 6.0,
        recuo_fundo_mm: float = 15.0, prof_rasgo_mm: float = 7.0,
        folga_fundo_mm: float = 2.0,
        offset: tuple[float, float, float] = (0.0, 0.0, 0.25),
        puxador_tipo: str = "alca",
        puxador_cor: str = "preto", puxador_pos: str = "padrao", desconto_perfil_mm: float = 35.0,
        perfil_modelo: str = "gola",
        tipo_fundo_gaveta: str = "rasgo",
        folga_corredica_mm: float = 26.0,
        material_gaveta: str | None = None,
        esp_gaveta_mm: float = 15.0,
        material_fita_gaveta: str | None = None,
        material_fundo_gaveta: str | None = None,
        esp_fundo_gaveta_mm: float = 6.0,
    ) -> list[Group]:
        ox, oy, oz = offset
        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor_frente = cls.get_material_color(mat_frente)

        groups, info = cls.build_caixa_modular(
            prefixo="Gabinete Banheiro",
            largura_mm=largura_mm,
            altura_mm=altura_mm,
            prof_mm=prof_mm,
            esp_mm=esp_mm,
            rodape_mm=0.0,
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
        L, A, P, E = info["L"], info["A"], info["P"], info["E"]
        largura_interna = info["largura_interna"]
        cor = info["cor"]
        desc_fundo = cls._calc_desconto_traseiro_fundo(tipo_fundo, esp_fundo_mm, recuo_fundo_mm)
        num_gav = 2
        alt_fg = (A - 0.009) / num_gav
        larg_frente = L - 0.006
        prof_gav = max(0.15, min(P - 0.050, P - desc_fundo - 0.015))
        larg_corredica = max(0.010, float(folga_corredica_mm) / 1000.0)
        larg_cg = max(0.08, largura_interna - larg_corredica)
        alt_cg = max(0.06, alt_fg - 0.040)

        # Materiais da gaveta
        mat_gav = material_gaveta or material
        mat_fg = material_fundo_gaveta or f"MDF Fundo {int(esp_fundo_gaveta_mm)}mm"

        for i in range(num_gav):
            z_fg = oz + 0.003 + (i * (alt_fg + 0.003))
            groups.append(create_board_group(
                f"Banheiro - Gaveta {i+1} Frente", (ox + 0.003, oy - E_frente, z_fg),
                (larg_frente, E_frente, alt_fg), mat_frente,
                fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="drawer", is_upper=False
            ))
            z_cg = z_fg + 0.015
            x_cg = ox + E + (larg_corredica / 2.0)
            y_cg = oy + 0.010

            gav_pieces = cls.build_caixa_gaveta(
                prefixo=f"Banheiro - Gaveta {i+1}",
                x_caixa=x_cg,
                y_caixa=y_cg,
                z_caixa=z_cg,
                larg_caixa=larg_cg,
                prof_caixa=prof_gav,
                alt_caixa=alt_cg,
                material_gaveta=mat_gav,
                esp_gaveta_mm=esp_gaveta_mm,
                material_fita_gaveta=material_fita_gaveta,
                tipo_fundo_gaveta=tipo_fundo_gaveta,
                material_fundo_gaveta=mat_fg,
                esp_fundo_gaveta_mm=esp_fundo_gaveta_mm,
            )
            groups.extend(gav_pieces)

        return groups

