# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations
import math
from typing import Any
from core.group import Group
from core.mesh import Mesh
from .builder_mesh_utils import create_board_group

class AereoTorreBuilder:
    """Construtor especializado para aéreos basculantes, nichos de microondas, torres quentes e caixas de geladeira."""

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
    def build_fundo_board(*args, **kwargs):
        from .builder import CabinetBuilder
        return CabinetBuilder.build_fundo_board(*args, **kwargs)

    @staticmethod
    def build_caixa_gaveta(*args, **kwargs):
        from .builder import CabinetBuilder
        return CabinetBuilder.build_caixa_gaveta(*args, **kwargs)

    @classmethod
    def build_aereo_basculante(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        esp_mm: float = 15.0, material: str = "MDF Branco TX 15mm",
        material_frentes: str | None = None, esp_frentes_mm: float | None = None,
        tipo_fundo: str = "rasgo", esp_fundo_mm: float = 6.0,
        recuo_fundo_mm: float = 15.0, prof_rasgo_mm: float = 7.0,
        folga_fundo_mm: float = 2.0,
        offset: tuple[float, float, float] = (0.0, 0.0, 1.5),
        puxador_tipo: str = "alca",
        puxador_cor: str = "preto", puxador_pos: str = "padrao", desconto_perfil_mm: float = 35.0,
        perfil_modelo: str = "gola",
    ) -> list[Group]:
        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor_frente = cls.get_material_color(mat_frente)

        groups, info = cls.build_caixa_modular(
            prefixo="Aereo Basc",
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

        alt_porta = A - 0.006
        groups.append(create_board_group(
            "Aereo Basc - Porta Basculante", (ox + 0.003, oy - E_frente, oz + 0.003),
            (L - 0.006, E_frente, alt_porta), mat_frente,
            fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
            puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="drawer", is_upper=True
        ))

        return groups

    @classmethod
    def build_aereo_basculante_duplo(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        esp_mm: float = 15.0, material: str = "MDF Branco TX 15mm",
        material_frentes: str | None = None, esp_frentes_mm: float | None = None,
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
        cor = cls.get_material_color(material)

        groups, info = cls.build_caixa_modular(
            prefixo="Aereo Duplo",
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

        desc_fundo = cls._calc_desconto_traseiro_fundo(tipo_fundo, esp_fundo_mm, recuo_fundo_mm)
        recuo_frontal_div = 0.020
        prof_div = max(0.10, P - desc_fundo - recuo_frontal_div)
        z_div = oz + (A / 2.0) - (E / 2.0)
        groups.append(create_board_group("Aereo Duplo - Divisao Central", (ox + E, oy + recuo_frontal_div, z_div), (largura_interna, prof_div, E), material, fita_c1=True, color=cor))

        alt_porta = (A - 0.009) / 2.0
        groups.append(create_board_group(
            "Aereo Duplo - Porta Basc Inf", (ox + 0.003, oy - E_frente, oz + 0.003),
            (L - 0.006, E_frente, alt_porta), mat_frente,
            fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
            puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="drawer", is_upper=True
        ))
        groups.append(create_board_group(
            "Aereo Duplo - Porta Basc Sup", (ox + 0.003, oy - E_frente, oz + 0.003 + alt_porta + 0.003),
            (L - 0.006, E_frente, alt_porta), mat_frente,
            fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
            puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="drawer", is_upper=True
        ))

        return groups

    @classmethod
    def build_aereo_microondas(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        esp_mm: float = 15.0, material: str = "MDF Branco TX 15mm",
        material_frentes: str | None = None, esp_frentes_mm: float | None = None,
        tipo_fundo: str = "rasgo", esp_fundo_mm: float = 6.0,
        recuo_fundo_mm: float = 15.0, prof_rasgo_mm: float = 7.0,
        folga_fundo_mm: float = 2.0,
        offset: tuple[float, float, float] = (0.0, 0.0, 1.4),
        puxador_tipo: str = "alca",
        puxador_cor: str = "preto", puxador_pos: str = "padrao", desconto_perfil_mm: float = 35.0,
        perfil_modelo: str = "gola",
        tipo_porta_superior: str = "basculante",
        num_portas: int = 1,
    ) -> list[Group]:
        ox, oy, oz = offset
        L, A, P, E = largura_mm / 1000.0, altura_mm / 1000.0, prof_mm / 1000.0, esp_mm / 1000.0
        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor = cls.get_material_color(material)
        cor_frente = cls.get_material_color(mat_frente)
        largura_interna = L - 2 * E
        altura_nicho_micro = 0.380
        groups = []

        groups.append(create_board_group("Aereo Micro - Lateral Esq", (ox, oy, oz), (E, P, A), material, fita_c1=True, fita_l1=True, color=cor))
        groups.append(create_board_group("Aereo Micro - Lateral Dir", (ox + L - E, oy, oz), (E, P, A), material, fita_c1=True, fita_l1=True, color=cor))
        groups.append(create_board_group("Aereo Micro - Base Projetada", (ox + E, oy - 0.03, oz), (largura_interna, P + 0.03, E), material, fita_c1=True, color=cor))
        groups.append(create_board_group("Aereo Micro - Tampo", (ox + E, oy, oz + A - E), (largura_interna, P, E), material, fita_c1=True, color=cor))

        z_div = oz + E + altura_nicho_micro
        groups.append(create_board_group("Aereo Micro - Divisao", (ox + E, oy, z_div), (largura_interna, P, E), material, fita_c1=True, color=cor))

        alt_sup = A - E - (E + altura_nicho_micro + E)
        if alt_sup > 0.10:
            fundo_grp = cls.build_fundo_board(
                prefixo="Aereo Micro",
                largura_interna_m=largura_interna,
                altura_interna_m=alt_sup,
                largura_total_m=L,
                altura_total_caixa_m=alt_sup + 2 * E,
                prof_total_m=P,
                esp_lateral_m=E,
                origin_caixa=(ox, oy, z_div + E),
                z_interno_base_m=z_div + E,
                tipo_fundo=tipo_fundo,
                esp_fundo_mm=esp_fundo_mm,
                recuo_fundo_mm=recuo_fundo_mm,
                prof_rasgo_mm=prof_rasgo_mm,
                folga_fundo_mm=folga_fundo_mm,
            )
            if fundo_grp:
                groups.append(fundo_grp)

            # Cobre a divisória e o tampo deixando folga técnica de 3mm no topo e na base
            z_porta = z_div + 0.003
            alt_porta = max(0.05, (oz + A - 0.003) - z_porta)
            alt_porta_mm = alt_porta * 1000.0
            is_basculante = (tipo_porta_superior == "basculante" or num_portas == 1)

            if is_basculante:
                # 1 Porta Basculante
                groups.append(create_board_group(
                    "Aereo Micro - Porta Superior Basculante",
                    (ox + 0.003, oy - E_frente, z_porta),
                    (L - 0.006, E_frente, alt_porta),
                    mat_frente,
                    fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                    color=cor_frente,
                    puxador_tipo=puxador_tipo, puxador_cor=puxador_cor,
                    puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm,
                    perfil_modelo=perfil_modelo,
                    door_side="drawer", is_upper=True
                ))
            else:
                # 2 Portas de Abrir / Giro
                from .machining import make_hinge_cup_holes
                ops_porta = [o.to_dict() for o in make_hinge_cup_holes(alt_porta_mm)]
                folga_entre_portas = 0.003
                larg_total_disponivel = L - 0.006 - folga_entre_portas
                larg_porta = max(0.10, larg_total_disponivel / 2.0)

                # Porta Esquerda
                groups.append(create_board_group(
                    "Aereo Micro - Porta Superior Esq",
                    (ox + 0.003, oy - E_frente, z_porta),
                    (larg_porta, E_frente, alt_porta),
                    mat_frente,
                    fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                    color=cor_frente,
                    puxador_tipo=puxador_tipo, puxador_cor=puxador_cor,
                    puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm,
                    perfil_modelo=perfil_modelo,
                    door_side="left", is_upper=True,
                    operacoes=ops_porta
                ))
                # Porta Direita
                x_dir = ox + 0.003 + larg_porta + folga_entre_portas
                groups.append(create_board_group(
                    "Aereo Micro - Porta Superior Dir",
                    (x_dir, oy - E_frente, z_porta),
                    (larg_porta, E_frente, alt_porta),
                    mat_frente,
                    fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                    color=cor_frente,
                    puxador_tipo=puxador_tipo, puxador_cor=puxador_cor,
                    puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm,
                    perfil_modelo=perfil_modelo,
                    door_side="right", is_upper=True,
                    operacoes=ops_porta
                ))

        return groups

    @classmethod
    def build_torre_quente(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
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
        tipo_fundo_gaveta: str = "rasgo",
        folga_corredica_mm: float = 26.0,
        material_gaveta: str | None = None,
        esp_gaveta_mm: float = 15.0,
        material_fita_gaveta: str | None = None,
        material_fundo_gaveta: str | None = None,
        esp_fundo_gaveta_mm: float = 6.0,
    ) -> list[Group]:
        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor_frente = cls.get_material_color(mat_frente)

        groups, info = cls.build_caixa_modular(
            prefixo="Torre Quente",
            largura_mm=largura_mm,
            altura_mm=altura_mm,
            prof_mm=prof_mm,
            esp_mm=esp_mm,
            rodape_mm=rodape_mm,
            tipo_topo="fechado",
            material=material,
            offset=offset,
            tem_fundo=False,  # O fundo da torre quente é dividido entre nichos e gavetas conforme geometria interna
        )
        ox, oy, oz = info["ox"], info["oy"], info["oz"]
        L, A, P, E, R = info["L"], info["A"], info["P"], info["E"], info["R"]
        altura_caixa = info["altura_caixa"]
        largura_interna = info["largura_interna"]
        cor = info["cor"]
        desc_fundo = cls._calc_desconto_traseiro_fundo(tipo_fundo, esp_fundo_mm, recuo_fundo_mm)
        alt_vao_gavetas = 0.550
        num_gav = 2
        alt_frente_gav = (alt_vao_gavetas - 0.009) / num_gav
        larg_frente = L - 0.006
        prof_gav = max(0.15, min(P - 0.050, P - desc_fundo - 0.015))
        larg_corredica = max(0.010, float(folga_corredica_mm) / 1000.0)
        larg_caixa_gav = max(0.08, largura_interna - larg_corredica)
        alt_caixa_gav = max(0.06, alt_frente_gav - 0.040)

        # Materiais da gaveta
        mat_gav = material_gaveta or material
        mat_fg = material_fundo_gaveta or f"MDF Fundo {int(esp_fundo_gaveta_mm)}mm"

        for i in range(num_gav):
            z_fg = oz + R + 0.003 + (i * (alt_frente_gav + 0.003))
            groups.append(create_board_group(
                f"Torre - Gaveta {i+1} Frente", (ox + 0.003, oy - E_frente, z_fg),
                (larg_frente, E_frente, alt_frente_gav), mat_frente,
                fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="drawer", is_upper=False
            ))
            z_cg = z_fg + 0.015
            x_cg = ox + E + (larg_corredica / 2.0)
            y_cg = oy + 0.010

            gav_pieces = cls.build_caixa_gaveta(
                prefixo=f"Torre - Gaveta {i+1}",
                x_caixa=x_cg,
                y_caixa=y_cg,
                z_caixa=z_cg,
                larg_caixa=larg_caixa_gav,
                prof_caixa=prof_gav,
                alt_caixa=alt_caixa_gav,
                material_gaveta=mat_gav,
                esp_gaveta_mm=esp_gaveta_mm,
                material_fita_gaveta=material_fita_gaveta,
                tipo_fundo_gaveta=tipo_fundo_gaveta,
                material_fundo_gaveta=mat_fg,
                esp_fundo_gaveta_mm=esp_fundo_gaveta_mm,
            )
            groups.extend(gav_pieces)

        z_div1 = oz + R + E + alt_vao_gavetas
        groups.append(create_board_group("Torre - Prateleira Apoio Forno", (ox + E, oy, z_div1), (largura_interna, P, E), material, fita_c1=True, color=cor))

        alt_nicho_forno = 0.600
        z_div2 = z_div1 + E + alt_nicho_forno
        groups.append(create_board_group("Torre - Prateleira Apoio Micro", (ox + E, oy, z_div2), (largura_interna, P, E), material, fita_c1=True, color=cor))

        alt_nicho_micro = 0.400
        z_div3 = z_div2 + E + alt_nicho_micro
        groups.append(create_board_group("Torre - Divisao Despensa", (ox + E, oy, z_div3), (largura_interna, P, E), material, fita_c1=True, color=cor))

        alt_despensa = (oz + A - E) - (z_div3 + E)
        if alt_despensa > 0.20:
            fundo_grp = cls.build_fundo_board(
                prefixo="Torre Despensa",
                largura_interna_m=largura_interna,
                altura_interna_m=alt_despensa,
                largura_total_m=L,
                altura_total_caixa_m=alt_despensa + 2 * E,
                prof_total_m=P,
                esp_lateral_m=E,
                origin_caixa=(ox, oy, z_div3 + E),
                z_interno_base_m=z_div3 + E,
                tipo_fundo=tipo_fundo,
                esp_fundo_mm=esp_fundo_mm,
                recuo_fundo_mm=recuo_fundo_mm,
                prof_rasgo_mm=prof_rasgo_mm,
                folga_fundo_mm=folga_fundo_mm,
            )
            if fundo_grp:
                groups.append(fundo_grp)
            alt_porta_d = alt_despensa - 0.006
            if L <= 0.60:
                groups.append(create_board_group(
                    "Torre - Porta Despensa", (ox + 0.003, oy - E_frente, z_div3 + E + 0.003),
                    (L - 0.006, E_frente, alt_porta_d), mat_frente,
                    fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                    puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="single", is_upper=True
                ))
            else:
                lp = (L - 0.009) / 2.0
                groups.append(create_board_group(
                    "Torre - Porta Despensa Esq", (ox + 0.003, oy - E_frente, z_div3 + E + 0.003),
                    (lp, E_frente, alt_porta_d), mat_frente,
                    fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                    puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="left", is_upper=True
                ))
                groups.append(create_board_group(
                    "Torre - Porta Despensa Dir", (ox + 0.003 + lp + 0.003, oy - E_frente, z_div3 + E + 0.003),
                    (lp, E_frente, alt_porta_d), mat_frente,
                    fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                    puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="right", is_upper=True
                ))

        return groups

    @classmethod
    def build_caixa_geladeira(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        esp_mm: float = 15.0, alt_nicho_geladeira_mm: float = 1800.0,
        num_portas: int = 2,
        tipo_porta_superior: str = "duas_portas",
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
        """Constrói o módulo Caixa para Geladeira (Módulo torre / fechamento).

        Composição:
        - 2 Laterais altas que vão até o chão (sem rodapé ou base inferior para permitir a geladeira entrar no vão).
        - 1 Tampo superior fechando a caixa.
        - 1 Prateleira horizontal estrutural (divisória) que delimita o topo do nicho da geladeira e a base do armário superior.
        - Fundo técnico no armário superior (maleiro).
        - Portas frontais no armário superior (1 porta basculante se num_portas==1 ou 2 portas de abrir).
        """
        ox, oy, oz = offset
        L = largura_mm / 1000.0
        A = altura_mm / 1000.0
        P = prof_mm / 1000.0
        E = esp_mm / 1000.0
        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor = cls.get_material_color(material)
        cor_frente = cls.get_material_color(mat_frente)

        largura_interna = max(0.20, L - 2.0 * E)
        alt_nicho = max(0.50, min(A - 0.20 - 2.0 * E, alt_nicho_geladeira_mm / 1000.0))

        groups: list[Group] = []

        # 1. Laterais Direita e Esquerda (vão completas até o piso oz)
        groups.append(create_board_group(
            "Geladeira - Lateral Esq", (ox, oy, oz), (E, P, A),
            material, fita_c1=True, fita_c2=True, fita_l1=True, color=cor
        ))
        groups.append(create_board_group(
            "Geladeira - Lateral Dir", (ox + L - E, oy, oz), (E, P, A),
            material, fita_c1=True, fita_c2=True, fita_l1=True, color=cor
        ))

        # 2. Tampo Superior (entre as laterais)
        groups.append(create_board_group(
            "Geladeira - Tampo Superior", (ox + E, oy, oz + A - E), (largura_interna, P, E),
            material, fita_c1=True, color=cor
        ))

        # 3. Prateleira Divisória Estrutural (Teto do nicho da geladeira / Base do maleiro)
        z_div = oz + alt_nicho
        groups.append(create_board_group(
            "Geladeira - Prateleira Divisoria", (ox + E, oy, z_div), (largura_interna, P, E),
            material, fita_c1=True, color=cor
        ))

        # 4. Armário Superior (Maleiro)
        # Altura interna do maleiro
        alt_maleiro_int = max(0.05, (oz + A - E) - (z_div + E))
        if alt_maleiro_int > 0.08:
            # Fundo técnico do maleiro
            if tipo_fundo != "sem_fundo":
                fundo_grp = cls.build_fundo_board(
                    prefixo="Geladeira Maleiro",
                    largura_interna_m=largura_interna,
                    altura_interna_m=alt_maleiro_int,
                    largura_total_m=L,
                    altura_total_caixa_m=alt_maleiro_int + 2.0 * E,
                    prof_total_m=P,
                    esp_lateral_m=E,
                    origin_caixa=(ox, oy, z_div + E),
                    z_interno_base_m=z_div + E,
                    tipo_fundo=tipo_fundo,
                    esp_fundo_mm=esp_fundo_mm,
                    recuo_fundo_mm=recuo_fundo_mm,
                    prof_rasgo_mm=prof_rasgo_mm,
                    folga_fundo_mm=folga_fundo_mm,
                )
                if fundo_grp:
                    groups.append(fundo_grp)

            # Portas do maleiro
            alt_porta = alt_maleiro_int + 2.0 * E - 0.006  # Cobre a divisória e o tampo deixando folga de 3mm topo e base
            z_porta = z_div + 0.003

            is_basculante = (num_portas == 1 or tipo_porta_superior in ("basculante", "1_porta", "porta_unica"))

            if is_basculante:
                # Porta Basculante / única
                larg_porta = L - 0.006
                groups.append(create_board_group(
                    "Geladeira - Porta Superior Basculante",
                    (ox + 0.003, oy - E_frente, z_porta),
                    (larg_porta, E_frente, alt_porta),
                    mat_frente,
                    fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                    color=cor_frente,
                    puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos,
                    desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                    door_side="flap", is_upper=True,
                ))
            else:
                # Duas portas de abrir com folga central de 3mm
                larg_cada_porta = (L - 0.009) / 2.0
                groups.append(create_board_group(
                    "Geladeira - Porta Maleiro Esq",
                    (ox + 0.003, oy - E_frente, z_porta),
                    (larg_cada_porta, E_frente, alt_porta),
                    mat_frente,
                    fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                    color=cor_frente,
                    puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos,
                    desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                    door_side="left", is_upper=True,
                ))
                groups.append(create_board_group(
                    "Geladeira - Porta Maleiro Dir",
                    (ox + 0.003 + larg_cada_porta + 0.003, oy - E_frente, z_porta),
                    (larg_cada_porta, E_frente, alt_porta),
                    mat_frente,
                    fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
                    color=cor_frente,
                    puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos,
                    desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                    door_side="right", is_upper=True,
                ))

        return groups
