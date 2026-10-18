# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations
import math
from typing import Any
from core.group import Group
from core.mesh import Mesh
from .builder_mesh_utils import create_board_group

class CantoEspecialBuilder:
    """Construtor especializado para cantos retos, cantos L, porta-temperos e balcões para forno embutido."""

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
    def build_canto_reto(
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
            prefixo="Canto Reto",
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
        larg_cego = min(0.50, P - 0.05)

        fundo_grp = cls.build_fundo_board(
            prefixo="Canto Reto",
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

        x_cego = ox + L - E - larg_cego
        groups.append(create_board_group("Canto Reto - Montante Cego", (x_cego, oy - E_frente, oz + R), (larg_cego, E_frente, altura_caixa), mat_frente, fita_c1=True, fita_l1=True, color=cor_frente))

        vao_porta = L - E - larg_cego - E
        recuo_topo = (recuo_porta_topo_mm / 1000.0) if travessa_frontal_em_pe else 0.0
        alt_porta = max(0.05, altura_caixa - recuo_topo - 0.006)
        if vao_porta > 0.15:
            groups.append(create_board_group(
                "Canto Reto - Porta", (ox + 0.003, oy - E_frente, oz + R + 0.003),
                (vao_porta - 0.006, E_frente, alt_porta), mat_frente,
                fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="right", is_upper=False
            ))

        desc_fundo = cls._calc_desconto_traseiro_fundo(tipo_fundo, esp_fundo_mm, recuo_fundo_mm)
        recuo_frontal_prat = 0.020
        prof_prat = max(0.10, P - desc_fundo - recuo_frontal_prat)
        groups.append(create_board_group("Canto Reto - Prateleira", (ox + E, oy + recuo_frontal_prat, oz + R + E + (altura_caixa - 2*E)/2.0), (largura_interna - 0.002, prof_prat, E), material, fita_c1=True, color=cor))

        return groups

    @classmethod
    def build_canto_l(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        larg_asa_mm: float = 550.0,
        esp_mm: float = 15.0, rodape_mm: float = 100.0,
        num_prateleiras: int = 1,
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
        gerar_furacao: bool = True,
        dispositivo_fixacao: str = "minifix_cavilha",
    ) -> list[Group]:
        """Gera um balcão de Canto L autêntico com 2 aberturas frontais em 90°, pilar/batente de quina interna,

        travessas estruturais (incluindo travessa central de apoio do tampo) e 2 portas de canto.
        """
        ox, oy, oz = offset
        Lx = largura_mm / 1000.0
        Ly = prof_mm / 1000.0
        A = altura_mm / 1000.0
        E = esp_mm / 1000.0
        R = rodape_mm / 1000.0
        altura_caixa = A - R

        # Profundidade padrão das duas alas (seções do balcão adjacentes)
        P_asa = min(larg_asa_mm / 1000.0, min(Lx, Ly) - 0.20)
        P_asa = max(0.35, P_asa)
        Px = P_asa
        Py = P_asa

        mat_frente = material_frentes or material
        E_frente = (esp_frentes_mm or esp_mm) / 1000.0
        cor = cls.get_material_color(material)
        cor_frente = cls.get_material_color(mat_frente)

        LTF = larg_travessa_frontal_mm / 1000.0
        LTT = larg_travessa_traseira_mm / 1000.0

        mat_fita_cx = material_fita_caixa or material
        cor_fita_cx = cls.get_material_color(mat_fita_cx) if material_fita_caixa else None

        mat_trav = material_travessas or material
        E_trav = (esp_travessas_mm / 1000.0) if (esp_travessas_mm and esp_travessas_mm > 0) else E
        cor_trav = cls.get_material_color(mat_trav)

        mat_fita_tr = material_fita_travessas or mat_trav
        cor_fita_tr = cls.get_material_color(mat_fita_tr) if material_fita_travessas else None

        modo_fita = (fita_travessas_modo or "frontal_1L").lower()
        if modo_fita == "sem_fita":
            f_c1_tf, f_c2_tf, f_l1_tf, f_l2_tf = False, False, False, False
            f_c1_tt, f_c2_tt, f_l1_tt, f_l2_tt = False, False, False, False
        elif modo_fita == "4l":
            f_c1_tf, f_c2_tf, f_l1_tf, f_l2_tf = True, True, True, True
            f_c1_tt, f_c2_tt, f_l1_tt, f_l2_tt = True, True, True, True
        elif modo_fita == "2l":
            f_c1_tf, f_c2_tf, f_l1_tf, f_l2_tf = True, True, False, False
            f_c1_tt, f_c2_tt, f_l1_tt, f_l2_tt = True, True, False, False
        else:
            f_c1_tf, f_c2_tf, f_l1_tf, f_l2_tf = True, False, False, False
            f_c1_tt, f_c2_tt, f_l1_tt, f_l2_tt = False, False, False, False

        groups = []

        # Usinagens de junção
        ops_lat = []
        if gerar_furacao:
            from .machining import make_cabinet_joint_holes
            usar_mini = ("minifix" in str(dispositivo_fixacao).lower())
            ops_lat.extend([
                o.to_dict() for o in make_cabinet_joint_holes(
                    comprimento_junta_mm=Px * 1000.0,
                    posicao_borda_mm=(esp_mm / 2.0),
                    face="traseira",
                    usar_minifix=usar_mini,
                )
            ])

        # ── 1. LATERAIS EXTERNAS DA CAIXARIA (Referência canto l.igz) ──────────
        # Lateral Esquerda inteiriça / Fundo Ala Y (ao longo de Y em X = ox):
        # Ocupa toda a extensão externa de Y: de oy até oy + Ly
        # Vai do chão (oz + R) até o topo (oz + A)
        groups.append(create_board_group(
            "Canto L - Lateral Esquerda Inteiriça",
            (ox, oy, oz + R),
            (E, Ly, altura_caixa),
            material, fita_c1=True, fita_l1=True, color=cor,
            material_fita=mat_fita_cx, cor_fita=cor_fita_cx, operacoes=ops_lat,
        ))

        # Lateral Direita da Ala X (ao longo de Y em X = ox + Lx - E):
        # Ocupa a profundidade Px da Ala X: de oy + Ly - Px até oy + Ly
        # Vai do chão (oz + R) até o topo (oz + A)
        groups.append(create_board_group(
            "Canto L - Lateral Direita",
            (ox + Lx - E, oy + Ly - Px, oz + R),
            (E, Px, altura_caixa),
            material, fita_c1=True, fita_l1=True, color=cor,
            material_fita=mat_fita_cx, cor_fita=cor_fita_cx, operacoes=ops_lat,
        ))

        # Fechamento Frontal Perpendicular da Ala Y (em Y = oy):
        # Fecha a extremidade frontal da Ala Y: de X = ox + E até ox + Py
        # Vai do chão (oz + R) até o topo (oz + A)
        # Borda +X (direita) fica aparente na fachada ao lado da Porta Ala Y -> fita_l2=True
        # Borda inferior (-Z) e superior (+Z) -> fita_c1=True
        larg_fechamento_frontal = max(0.05, Py - E)
        groups.append(create_board_group(
            "Canto L - Lateral Frontal Ala Y",
            (ox + E, oy, oz + R),
            (larg_fechamento_frontal, E, altura_caixa),
            material, fita_c1=True, fita_l1=True, fita_l2=True, color=cor,
            material_fita=mat_fita_cx, cor_fita=cor_fita_cx, operacoes=ops_lat,
        ))

        # ── 2. BASES INFERIORES EM L (Referência canto l.igz) ─────────────────
        # Base da Ala X:
        # Fica entre as laterais externas: de X = ox + E até ox + Lx - E
        # Profundidade Px: de Y = oy + Ly - Px até oy + Ly
        # Borda frontal em -Y fica voltada para as portas -> fita_c1=True
        larg_base_x = max(0.10, Lx - 2 * E)
        groups.append(create_board_group(
            "Canto L - Base Ala X",
            (ox + E, oy + Ly - Px, oz + R),
            (larg_base_x, Px, E),
            material, fita_c1=True, color=cor,
            material_fita=mat_fita_cx, cor_fita=cor_fita_cx,
        ))

        # Base da Ala Y:
        # Encaixa perpendicularmente na Base X:
        # Em X ocupa de ox + E até ox + Py
        # Em Y ocupa de oy + E até oy + Ly - Px
        # Borda frontal em +X fica voltada para a Porta Ala Y -> fita_l2=True
        larg_base_y = max(0.05, Py - E)
        prof_base_y = max(0.05, Ly - Px - E)
        groups.append(create_board_group(
            "Canto L - Base Ala Y",
            (ox + E, oy + E, oz + R),
            (larg_base_y, prof_base_y, E),
            material, fita_c1=True, fita_l2=True, color=cor,
            material_fita=mat_fita_cx, cor_fita=cor_fita_cx,
        ))

        # ── 3. FUNDO TRASEIRO DA ALA X ───────────────────────────────────────
        if tipo_fundo != "sem_fundo":
            E_fundo = esp_fundo_mm / 1000.0
            recuo_m = recuo_fundo_mm / 1000.0
            py_fundo = (oy + Ly - recuo_m - E_fundo) if tipo_fundo == "rasgo" else (oy + Ly - E_fundo)
            groups.append(create_board_group(
                "Canto L - Fundo Traseiro",
                (ox + E, py_fundo, oz + R),
                (larg_base_x, E_fundo, altura_caixa),
                material, color=cor,
            ))

        # ── 4. TRAVESSAS SUPERIORES ESTRUTURAIS EM PÉ (Apoio de Tampo) ────────
        # ── 4. TRAVESSAS SUPERIORES ESTRUTURAIS (Horizontais / Verticais) ──────
        # Travessas Frontais (Ala X e Ala Y):
        if travessa_frontal_em_pe:
            alt_trav_f = LTF if LTF > 0.02 else 0.070
            z_trav_f = oz + R + altura_caixa - alt_trav_f
            # Ala X (em pé vertical em Y = oy + Ly - Px):
            groups.append(create_board_group(
                "Canto L - Travessa Frontal Ala X",
                (ox + E, oy + Ly - Px, z_trav_f),
                (larg_base_x, E_trav, alt_trav_f),
                mat_trav, fita_c1=f_c1_tf, fita_c2=f_c2_tf, fita_l1=f_l1_tf, fita_l2=f_l2_tf, color=cor_trav,
                material_fita=mat_fita_tr, cor_fita=cor_fita_tr,
            ))
            # Ala Y (em pé vertical em X = ox + Py - E_trav):
            groups.append(create_board_group(
                "Canto L - Travessa Frontal Ala Y",
                (ox + Py - E_trav, oy + E, z_trav_f),
                (E_trav, prof_base_y, alt_trav_f),
                mat_trav, fita_c1=f_c1_tf, fita_c2=f_c2_tf, fita_l1=f_l1_tf, fita_l2=f_l2_tf, color=cor_trav,
                material_fita=mat_fita_tr, cor_fita=cor_fita_tr,
            ))
        else:
            # Travessas deitadas / horizontais no topo (Z = topo - E_trav)
            z_trav_f = oz + R + altura_caixa - E_trav
            # Ala X (deitada no topo em Y = oy + Ly - Px):
            groups.append(create_board_group(
                "Canto L - Travessa Frontal Ala X",
                (ox + E, oy + Ly - Px, z_trav_f),
                (larg_base_x, LTF, E_trav),
                mat_trav, fita_c1=f_c1_tf, fita_c2=f_c2_tf, fita_l1=f_l1_tf, fita_l2=f_l2_tf, color=cor_trav,
                material_fita=mat_fita_tr, cor_fita=cor_fita_tr,
            ))
            # Ala Y (deitada no topo em X = ox + Py - LTF):
            groups.append(create_board_group(
                "Canto L - Travessa Frontal Ala Y",
                (ox + Py - LTF, oy + E, z_trav_f),
                (LTF, prof_base_y, E_trav),
                mat_trav, fita_c1=f_c1_tf, fita_c2=f_c2_tf, fita_l1=f_l1_tf, fita_l2=f_l2_tf, color=cor_trav,
                material_fita=mat_fita_tr, cor_fita=cor_fita_tr,
            ))

        # Travessa Traseira da Ala X (em pé vertical ou deitada horizontal):
        if travessa_traseira_em_pe:
            alt_trav_t = LTT if LTT > 0.02 else 0.070
            z_trav_t = oz + R + altura_caixa - alt_trav_t
            groups.append(create_board_group(
                "Canto L - Travessa Traseira Ala X",
                (ox + E, oy + Ly - E_trav, z_trav_t),
                (larg_base_x, E_trav, alt_trav_t),
                mat_trav, fita_c1=f_c1_tt, fita_c2=f_c2_tt, fita_l1=f_l1_tt, fita_l2=f_l2_tt, color=cor_trav,
                material_fita=mat_fita_tr, cor_fita=cor_fita_tr,
            ))
        else:
            z_trav_t = oz + R + altura_caixa - E_trav
            groups.append(create_board_group(
                "Canto L - Travessa Traseira Ala X",
                (ox + E, oy + Ly - LTT, z_trav_t),
                (larg_base_x, LTT, E_trav),
                mat_trav, fita_c1=f_c1_tt, fita_c2=f_c2_tt, fita_l1=f_l1_tt, fita_l2=f_l2_tt, color=cor_trav,
                material_fita=mat_fita_tr, cor_fita=cor_fita_tr,
            ))

        # ── 5. PORTAS / FRENTES DE CANTO L (2 Portas em 90° abrindo para lados opostos) ─
        # Quando as travessas frontais estão em pé, desconta o recuo do topo para pegada de mão / perfil
        recuo_topo = (recuo_porta_topo_mm / 1000.0) if travessa_frontal_em_pe else 0.0
        alt_porta = max(0.10, altura_caixa - recuo_topo - 0.006)
        z_porta = oz + R + 0.003
        folga_canto = 0.003  # Folga técnica na quina interna de 90°

        # Porta 2 (Ala Y - plano YZ, na face frontal da Ala Y):
        # Fica em X = ox + Py (com espessura de ox + Py até ox + Py + E_frente)
        # O vão da Ala Y vai de Y = oy + E até oy + Ly - Px
        # Termina em Y = oy + Ly - Px - folga_canto
        # Abertura para o lado externo oposto (-Y / lateral externa): dobradiças na extremidade frontal ("right"),
        # puxador na extremidade da quina (+Y)
        larg_vao_y = max(0.10, Ly - Px - E)
        larg_porta_y = max(0.08, larg_vao_y - folga_canto - 0.002)
        y_porta_y = oy + E + 0.002
        groups.append(create_board_group(
            "Canto L - Porta Ala Y",
            (ox + Py, y_porta_y, z_porta),
            (E_frente, larg_porta_y, alt_porta),
            mat_frente, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
            puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos,
            desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
            door_side="left", is_upper=False,
        ))

        # Porta 1 (Ala X - plano XZ, na face frontal da Ala X):
        # Fica em Y = oy + Ly - Px - E_frente (com espessura de Y = oy + Ly - Px - E_frente até oy + Ly - Px)
        # Para NÃO encavalar nem colidir com a Porta Ala Y (que ocupa até X = ox + Py + E_frente),
        # a Porta Ala X inicia em X = ox + Py + E_frente + folga_canto e vai até a lateral direita (ox + Lx - E)
        # Abertura para o lado externo (+X): dobradiças à direita ("right"), puxador na extremidade da quina (esquerda)
        x_porta_x = ox + Py + E_frente + folga_canto
        larg_porta_x = max(0.08, (ox + Lx - E - 0.002) - x_porta_x)
        groups.append(create_board_group(
            "Canto L - Porta Ala X",
            (x_porta_x, oy + Ly - Px - E_frente, z_porta),
            (larg_porta_x, E_frente, alt_porta),
            mat_frente, fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
            puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos,
            desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
            door_side="right", is_upper=False,
        ))

        # ── 6. PRATELEIRAS INTERNAS EM L ──────────────────────────────────────
        if num_prateleiras > 0:
            z_prat = oz + R + E + (altura_caixa - 2 * E) / 2.0
            desc_fundo = cls._calc_desconto_traseiro_fundo(tipo_fundo, esp_fundo_mm, recuo_fundo_mm)
            # Prateleira Ala X
            groups.append(create_board_group(
                "Canto L - Prateleira Ala X",
                (ox + Py, oy + Ly - Px + 0.020, z_prat),
                (max(0.05, Lx - Py - E - 0.004), max(0.05, Px - desc_fundo - 0.024), E),
                material, fita_c1=True, color=cor,
            ))
            # Prateleira Ala Y
            groups.append(create_board_group(
                "Canto L - Prateleira Ala Y",
                (ox + E + desc_fundo, oy + E + 0.020, z_prat),
                (max(0.05, Py - desc_fundo - E), max(0.05, Ly - Px - E - 0.024), E),
                material, fita_c1=True, color=cor,
            ))

        # ── 7. RODAPÉ FRONTAL EM L ────────────────────────────────────────────
        if R > 0.01:
            # Rodapé sob a Ala X
            groups.append(create_board_group(
                "Canto L - Rodape Ala X",
                (ox + Py, oy + Ly - Px + 0.050, oz),
                (max(0.05, Lx - Py), E, R),
                material, color=cor,
            ))
            # Rodapé sob a Ala Y
            groups.append(create_board_group(
                "Canto L - Rodape Ala Y",
                (ox + Py - 0.050 - E, oy + E, oz),
                (E, max(0.05, Ly - Px - E), R),
                material, color=cor,
            ))

        return groups

    @classmethod
    def build_porta_tempero(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        esp_mm: float = 15.0, rodape_mm: float = 100.0,
        material: str = "MDF Branco TX 15mm", material_frentes: str | None = None,
        esp_frentes_mm: float | None = None,
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
        gerar_furacao: bool = True,
        dispositivo_fixacao: str = "minifix_cavilha",
    ) -> list[Group]:
        groups, info = cls.build_caixa_inferior(
            prefixo="Porta-Tempero",
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

        recuo_topo = (recuo_porta_topo_mm / 1000.0) if travessa_frontal_em_pe else 0.0
        alt_frente = max(0.05, altura_caixa - recuo_topo - 0.006)
        groups.append(create_board_group(
            "Porta-Tempero - Frente", (ox + 0.003, oy - E_frente, oz + R + 0.003),
            (L - 0.006, E_frente, alt_frente), mat_frente,
            fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
            puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos, desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo, door_side="drawer", is_upper=False
        ))

        z_p1 = oz + R + E + 0.05
        z_p2 = oz + R + E + (altura_caixa * 0.55)
        prof_util = P - 0.05
        for idx, zp in enumerate([z_p1, z_p2], start=1):
            groups.append(create_board_group(f"Porta-Tempero - Base Bandeja {idx}", (ox + E + 0.005, oy + 0.02, zp), (largura_interna - 0.01, prof_util, E), material, fita_c1=True, color=cor))
            groups.append(create_board_group(f"Porta-Tempero - Aba Contencao {idx}", (ox + E + 0.005, oy + 0.02, zp + E), (largura_interna - 0.01, E, 0.05), material, fita_c1=True, color=cor))

        return groups

    @classmethod
    def build_balcao_forno(
        cls, largura_mm: float, altura_mm: float, prof_mm: float,
        esp_mm: float = 15.0, rodape_mm: float = 100.0,
        material: str = "MDF Branco TX 15mm", material_frentes: str | None = None,
        esp_frentes_mm: float | None = None,
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        puxador_tipo: str = "alca",
        puxador_cor: str = "preto", puxador_pos: str = "padrao", desconto_perfil_mm: float = 35.0,
        perfil_modelo: str = "gola",
        larg_travessa_frontal_mm: float = 70.0,
        larg_travessa_traseira_mm: float = 70.0,
        travessa_frontal_em_pe: bool = True,
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
        tem_gaveta: bool = True,
        alt_gaveta_mm: float = 150.0,
        tipo_fundo_gaveta: str = "rasgo",
        folga_corredica_mm: float = 26.0,
        material_gaveta: str | None = None,
        esp_gaveta_mm: float = 15.0,
        material_fita_gaveta: str | None = None,
        material_fundo_gaveta: str | None = None,
        esp_fundo_gaveta_mm: float = 6.0,
    ) -> list[Group]:
        """Gera caixa padrão de balcão inferior para forno com frente cega em MDF e gaveta opcional."""
        groups, info = cls.build_caixa_inferior(
            prefixo="Balcao Forno",
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

        # Altura útil total interna
        alt_util_interna = altura_caixa - E  # base inferior desconta E

        # 1. Definição da altura do gavetão e apoio do forno
        if tem_gaveta:
            # Altura do vão da gaveta configurável (padrão ~150mm a 200mm)
            alt_gaveta_m = max(0.080, min(alt_util_interna - 0.450, float(alt_gaveta_mm) / 1000.0))
            alt_frente_gav = alt_gaveta_m - 0.006
            z_fg = oz + R + 0.003

            # Prateleira Estrutural de Apoio do Forno (acima do gavetão)
            z_apoio = oz + R + E + alt_gaveta_m
            groups.append(create_board_group(
                "Balcao Forno - Base Apoio Forno", (ox + E, oy, z_apoio),
                (largura_interna, P, E), material, fita_c1=True, color=cor
            ))

            # Gaveta - Frente em MDF
            groups.append(create_board_group(
                "Balcao Forno - Gaveta Frente", (ox + 0.003, oy - E_frente, z_fg),
                (L - 0.006, E_frente, alt_frente_gav), mat_frente,
                fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True, color=cor_frente,
                puxador_tipo=puxador_tipo, puxador_cor=puxador_cor, puxador_pos=puxador_pos,
                desconto_perfil_mm=desconto_perfil_mm, perfil_modelo=perfil_modelo,
                door_side="drawer", is_upper=False
            ))

            # Gaveta - Caixa interna
            larg_corredica = max(0.010, float(folga_corredica_mm) / 1000.0)
            larg_caixa_gav = max(0.08, largura_interna - larg_corredica)
            alt_caixa_gav = max(0.06, alt_frente_gav - 0.040)
            prof_gav = max(0.15, P - 0.060)

            mat_gav = material_gaveta or material
            mat_fg = material_fundo_gaveta or f"MDF Fundo {int(esp_fundo_gaveta_mm)}mm"

            gav_pieces = cls.build_caixa_gaveta(
                prefixo="Balcao Forno - Gaveta",
                x_caixa=ox + E + (larg_corredica / 2.0),
                y_caixa=oy + 0.010,
                z_caixa=z_fg + 0.015,
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
        else:
            # Sem gaveta: o forno apoia diretamente sobre a base inferior
            z_apoio = oz + R
            alt_gaveta_m = 0.0

        # 2. Frente Cega / Painel para Embutir o Forno
        # Em marcenaria padrão, o balcão de forno tem uma frente cega (chapa de MDF)
        # onde na montagem/obra é feito o recorte para embutir o forno.
        # Se a travessa frontal estiver em pé, deve obedecer à folga/rebaixo no topo (recuo_porta_topo_mm).
        recuo_topo = (recuo_porta_topo_mm / 1000.0) if travessa_frontal_em_pe else 0.0

        # Se tem gaveta, a frente cega começa acima da prateleira de apoio (z_apoio + E).
        # Se não tem gaveta, a frente cega começa na base inferior (oz + R + 0.003).
        z_frente_cega = (z_apoio + E) if tem_gaveta else (oz + R + 0.003)
        topo_frente_cega = (oz + R + altura_caixa) - recuo_topo - 0.003
        alt_frente_cega = max(0.080, topo_frente_cega - z_frente_cega)

        groups.append(create_board_group(
            "Balcao Forno - Frente Cega",
            (ox + 0.003, oy - E_frente, z_frente_cega),
            (L - 0.006, E_frente, alt_frente_cega),
            mat_frente,
            fita_c1=True, fita_c2=True, fita_l1=True, fita_l2=True,
            color=cor_frente,
        ))

        return groups

