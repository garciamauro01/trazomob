# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Caixaria e componentes estruturais do CabinetBuilder."""
from __future__ import annotations

from typing import Any

from core.group import Group

from ..builders.mesh_utils import create_board_group
from ..domain.materials_catalog import get_material_color


class CaixaMixin:
    """Fundos, gavetas e a caixa modular base dos modulos."""

    @staticmethod
    def get_material_color(material: str) -> tuple[float, float, float]:
        return get_material_color(material)

    @classmethod
    def _calc_desconto_traseiro_fundo(
        cls, tipo_fundo: str = "rasgo", esp_fundo_mm: float = 6.0, recuo_fundo_mm: float = 15.0
    ) -> float:
        """Calcula o desconto traseiro (em metros) até a face frontal do fundo.

        Garante que partes internas (prateleiras, divisórias, gavetas) fiquem rigorosamente
        no vão útil interno, encostando na face do fundo sem nunca invadi-lo ou ultrapassá-lo.
        """
        if tipo_fundo == "rasgo":
            return (recuo_fundo_mm + esp_fundo_mm) / 1000.0
        elif tipo_fundo == "sobreposto":
            return esp_fundo_mm / 1000.0
        return 0.0

    @classmethod
    def build_fundo_board(
        cls,
        prefixo: str,
        largura_interna_m: float,
        altura_interna_m: float,
        largura_total_m: float,
        altura_total_caixa_m: float,
        prof_total_m: float,
        esp_lateral_m: float,
        origin_caixa: tuple[float, float, float],
        z_interno_base_m: float,
        tipo_fundo: str = "rasgo",
        esp_fundo_mm: float = 6.0,
        recuo_fundo_mm: float = 15.0,
        prof_rasgo_mm: float = 7.0,
        folga_fundo_mm: float = 2.0,
        material_fundo: str | None = None,
    ) -> Group | None:
        """Gera a peça de fundo com os parâmetros de marcenaria TrazoMob.

        Suporta:
        - 'rasgo': Canal / rasgo embutido nas laterais e base, com recuo traseiro.
        - 'sobreposto': Chapa pregada / parafusada por trás.
        - 'sem_fundo': Sem geração de peça.
        """
        if tipo_fundo == "sem_fundo":
            return None

        ox, oy, oz_caixa = origin_caixa
        E = esp_lateral_m
        E_fundo = esp_fundo_mm / 1000.0
        prof_r_m = prof_rasgo_mm / 1000.0
        folga_m = folga_fundo_mm / 1000.0
        recuo_m = recuo_fundo_mm / 1000.0

        if tipo_fundo == "sobreposto":
            # Sobreposto: cobre a traseira total (menos folga de esquadro)
            comp_m = max(0.05, altura_total_caixa_m - folga_m)
            larg_m = max(0.05, largura_total_m - folga_m)
            px = ox + (folga_m / 2.0)
            py = oy + prof_total_m - E_fundo
            pz = oz_caixa + (folga_m / 2.0)
        else:
            # Canal / Rasgo: avança nos rasgos das laterais e base e desconta folga
            larg_chapa_mm = (largura_interna_m * 1000.0) + (2.0 * prof_rasgo_mm) - folga_fundo_mm
            alt_chapa_mm = (altura_interna_m * 1000.0) + (2.0 * prof_rasgo_mm) - folga_fundo_mm
            larg_m = max(0.05, larg_chapa_mm / 1000.0)
            comp_m = max(0.05, alt_chapa_mm / 1000.0)
            px = ox + E - prof_r_m + (folga_m / 2.0)
            py = oy + prof_total_m - recuo_m - E_fundo
            pz = z_interno_base_m - prof_r_m + (folga_m / 2.0)

        nome = f"{prefixo} - Fundo {int(esp_fundo_mm)}mm"
        if material_fundo:
            mat = material_fundo
        elif esp_fundo_mm <= 6.0:
            mat = f"MDF Fundo {int(esp_fundo_mm)}mm"
        else:
            mat = f"MDF Branco TX {int(esp_fundo_mm)}mm"

        return create_board_group(
            name=nome,
            origin=(px, py, pz),
            size=(larg_m, E_fundo, comp_m),
            material=mat,
            color=(0.88, 0.88, 0.88),
        )

    @classmethod
    def build_caixa_gaveta(
        cls,
        prefixo: str,
        x_caixa: float,
        y_caixa: float,
        z_caixa: float,
        larg_caixa: float,
        prof_caixa: float,
        alt_caixa: float,
        material_gaveta: str = "MDF Branco TX 15mm",
        esp_gaveta_mm: float = 15.0,
        material_fita_gaveta: str | None = None,
        tipo_fundo_gaveta: str = "rasgo",
        material_fundo_gaveta: str = "MDF Fundo 6mm",
        esp_fundo_gaveta_mm: float = 6.0,
    ) -> list[Group]:
        """Gera as 5 peças da caixa de gaveta interna (2 Laterais, Contra-frente frontal, Contra-frente traseira e Fundo).

        Suporta:
        - tipo_fundo_gaveta: 'rasgo' (rebaixo embutido com fundo passando nas ranhuras) ou 'por_baixo' (fundo fixado por baixo da caixa).
        - Espessura e material configuráveis para as laterais/contra-frentes da gaveta.
        - Fita de borda da gaveta personalizável (aplicada no topo / bordo aparente).
        - Espessura e material configuráveis para a chapa do fundo.
        """
        E_g = (esp_gaveta_mm / 1000.0) if (esp_gaveta_mm and esp_gaveta_mm > 0) else 0.015
        E_fg = (esp_fundo_gaveta_mm / 1000.0) if (esp_fundo_gaveta_mm and esp_fundo_gaveta_mm > 0) else 0.006
        cor_g = cls.get_material_color(material_gaveta)
        cor_fita_g = cls.get_material_color(material_fita_gaveta) if material_fita_gaveta else None
        cor_fg = cls.get_material_color(material_fundo_gaveta)

        mat_fita_g = material_fita_gaveta or material_gaveta
        larg_cf = max(0.04, larg_caixa - 2.0 * E_g)

        pieces: list[Group] = []

        # 1. Lateral Esquerda e Lateral Direita (espessura em X: tamanho E_g x prof_caixa x alt_caixa)
        # No _make_board_mesh para chapa lateral:
        # - cor_l2 é o topo (+Z, face superior aparente da gaveta)
        # - cor_c1 é a face frontal (-Y)
        # - Comprimento (maior dimensão da fita) é prof_caixa (ao longo de Y).
        # Para que a fita apareça tanto visualmente no 3D quanto na lista do plano de corte (TrazoMob),
        # definimos fita_c1=True (comprimento) e fita_l2=True (topo +Z).
        pieces.append(create_board_group(
            name=f"{prefixo} - Lat Esq",
            origin=(x_caixa, y_caixa, z_caixa),
            size=(E_g, prof_caixa, alt_caixa),
            material=material_gaveta,
            fita_c1=True,
            fita_l2=True,
            color=cor_g,
            material_fita=mat_fita_g,
            cor_fita=cor_fita_g,
        ))
        pieces.append(create_board_group(
            name=f"{prefixo} - Lat Dir",
            origin=(x_caixa + larg_caixa - E_g, y_caixa, z_caixa),
            size=(E_g, prof_caixa, alt_caixa),
            material=material_gaveta,
            fita_c1=True,
            fita_l2=True,
            color=cor_g,
            material_fita=mat_fita_g,
            cor_fita=cor_fita_g,
        ))

        # 2. Contra-frente Dianteira e Traseira (espessura em Y: tamanho larg_cf x E_g x alt_cf)
        # No _make_board_mesh para chapa frontal/contra-frente:
        # - cor_c2 é o topo (+Z, face superior aparente da gaveta)
        # - Comprimento (maior dimensão) é larg_cf (ao longo de X).
        # Definimos fita_c1=True e fita_c2=True para fitar a borda superior aparente.
        alt_cf = max(0.04, alt_caixa - 0.015)
        pieces.append(create_board_group(
            name=f"{prefixo} - Contra-frente Diant",
            origin=(x_caixa + E_g, y_caixa, z_caixa),
            size=(larg_cf, E_g, alt_cf),
            material=material_gaveta,
            fita_c1=True,
            fita_c2=True,
            color=cor_g,
            material_fita=mat_fita_g,
            cor_fita=cor_fita_g,
        ))
        pieces.append(create_board_group(
            name=f"{prefixo} - Contra-frente Tras",
            origin=(x_caixa + E_g, y_caixa + prof_caixa - E_g, z_caixa),
            size=(larg_cf, E_g, alt_cf),
            material=material_gaveta,
            fita_c1=True,
            fita_c2=True,
            color=cor_g,
            material_fita=mat_fita_g,
            cor_fita=cor_fita_g,
        ))

        # 3. Fundo da Gaveta
        modo_fundo = (tipo_fundo_gaveta or "rasgo").lower()
        if modo_fundo in ("por_baixo", "baixo", "pregado", "aparafusado"):
            # Fundo por baixo: cobre toda a base da caixa de gaveta
            fundo_orig = (x_caixa, y_caixa, z_caixa)
            fundo_size = (larg_caixa, prof_caixa, E_fg)
        else:
            # Canal / Rasgo lateral: fica elevado em relação à base e entra nas ranhuras (ranhura padrão 6mm / folga 1mm)
            prof_rasgo_m = 0.006
            dist_base_m = 0.010
            larg_fundo_m = max(0.05, larg_caixa - 2.0 * E_g + 2.0 * prof_rasgo_m - 0.001)
            prof_fundo_m = max(0.05, prof_caixa - 2.0 * E_g + 2.0 * prof_rasgo_m - 0.001)
            fundo_orig = (x_caixa + E_g - prof_rasgo_m + 0.0005, y_caixa + E_g - prof_rasgo_m + 0.0005, z_caixa + dist_base_m)
            fundo_size = (larg_fundo_m, prof_fundo_m, E_fg)

        pieces.append(create_board_group(
            name=f"{prefixo} - Fundo {int(esp_fundo_gaveta_mm)}mm",
            origin=fundo_orig,
            size=fundo_size,
            material=material_fundo_gaveta,
            color=cor_fg,
        ))

        return pieces

    @classmethod
    def build_caixa_modular(
        cls,
        prefixo: str,
        largura_mm: float,
        altura_mm: float,
        prof_mm: float,
        esp_mm: float = 15.0,
        rodape_mm: float = 0.0,
        tipo_topo: str = "fechado",  # "fechado" (tampo superior) ou "travessas" (travessas frontal/traseira)
        material: str = "MDF Branco TX 15mm",
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        # Parâmetros de Travessas (quando tipo_topo == "travessas")
        larg_travessa_frontal_mm: float = 70.0,
        larg_travessa_traseira_mm: float = 70.0,
        travessa_frontal_em_pe: bool = False,
        travessa_traseira_em_pe: bool = False,
        material_travessas: str | None = None,
        esp_travessas_mm: float | None = None,
        fita_travessas_modo: str = "frontal_1L",
        fita_travessas_faces: dict[str, bool] | None = None,
        material_fita_travessas: str | None = None,
        # Fita da caixaria (Laterais, Base e Tampo)
        fita_caixa_modo: str = "frontal_1L",
        material_fita_caixa: str | None = None,
        # Parâmetros do Fundo TrazoMob
        tem_fundo: bool = True,
        tipo_fundo: str = "rasgo",  # "rasgo", "sobreposto", "sem_fundo"
        esp_fundo_mm: float = 6.0,
        recuo_fundo_mm: float = 15.0,
        prof_rasgo_mm: float = 7.0,
        folga_fundo_mm: float = 2.0,
        material_fundo: str | None = None,
        # Furações técnicas e Dispositivos de Junção
        gerar_furacao: bool = True,
        dispositivo_fixacao: str = "minifix_cavilha",
    ) -> tuple[list[Group], dict]:
        """Motor central e universal para construção paramétrica de caixarias de marcenaria.

        Padroniza a fabricação de caixas tanto para armários, roupeiros e aéreos (com tampo fechado)
        quanto para balcões inferiores de cozinha (com travessas superiores).

        Gera:
        - Lateral Esquerda e Lateral Direita
        - Base Inferior
        - Tampo Superior Fechado (se tipo_topo == 'fechado')
          OU Travessas Frontal e Traseira (se tipo_topo == 'travessas')
        - Rodapé Frontal estrutural (se rodape_mm > 0)
        - Fundo TrazoMob embutido/sobreposto (se tem_fundo e tipo_fundo != 'sem_fundo')
        - Operações de Usinagem completas:
          * Junções por Minifix / Cavilha / Confirmat (nas laterais para base e topo)
          * Rasgos/ranhuras do fundo de 6mm (nas laterais, base e tampo)
        """
        ox, oy, oz = offset
        L, A, P, E, R = largura_mm / 1000.0, altura_mm / 1000.0, prof_mm / 1000.0, esp_mm / 1000.0, rodape_mm / 1000.0
        cor = cls.get_material_color(material)
        altura_caixa = A - R
        largura_interna = L - 2 * E
        LTF = larg_travessa_frontal_mm / 1000.0
        LTT = larg_travessa_traseira_mm / 1000.0
        E_trav = (esp_travessas_mm / 1000.0) if esp_travessas_mm is not None else E

        # Resolução da fita de borda da caixaria (Laterais, Base e Tampo)
        modo_fita_cx = (fita_caixa_modo or "frontal_1L").lower()
        if modo_fita_cx == "sem_fita":
            f_cx_c1, f_cx_c2, f_cx_l1, f_cx_l2 = False, False, False, False
        elif modo_fita_cx == "4l":
            f_cx_c1, f_cx_c2, f_cx_l1, f_cx_l2 = True, True, True, True
        elif modo_fita_cx == "2l":
            # 2 bordos longos (frontal e traseiro)
            f_cx_c1, f_cx_c2, f_cx_l1, f_cx_l2 = True, True, False, False
        else:
            # "frontal_1L" (Padrão marcenaria: topo/frente visível)
            f_cx_c1, f_cx_c2, f_cx_l1, f_cx_l2 = True, False, True, False

        # Material e cor da fita de borda da caixa
        mat_fita_cx = material_fita_caixa or material
        cor_fita_cx = cls.get_material_color(mat_fita_cx) if material_fita_caixa else None

        # Furações dos dispositivos de montagem e usinagens de rasgo nas peças
        ops_lateral = []
        ops_base = []
        ops_tampo = []

        eff_tipo_fundo = "sem_fundo" if not tem_fundo else tipo_fundo

        if gerar_furacao:
            from ..production.machining import make_cabinet_joint_holes, make_back_panel_groove
            usar_mini = ("minifix" in str(dispositivo_fixacao).lower())

            # 1. Furação de junção da base inferior na lateral
            # make_cabinet_joint_holes retorna conectores ao longo da profundidade da junta
            ops_lateral.extend([
                o.to_dict() for o in make_cabinet_joint_holes(
                    comprimento_junta_mm=prof_mm,
                    posicao_borda_mm=(esp_mm / 2.0),
                    face="traseira",
                    usar_minifix=usar_mini,
                )
            ])

            # 2. Se for tampo fechado, furação de junção do topo superior na lateral
            if tipo_topo == "fechado":
                pos_topo_mm = max(0.0, (altura_caixa * 1000.0) - (esp_mm / 2.0))
                pos_minifix_topo_mm = max(0.0, (altura_caixa * 1000.0) - 34.0)
                for o in make_cabinet_joint_holes(
                    comprimento_junta_mm=prof_mm,
                    posicao_borda_mm=pos_topo_mm,
                    face="traseira",
                    usar_minifix=usar_mini,
                ):
                    od = o.to_dict()
                    if "minifix" in str(od.get("descricao", "")).lower():
                        od["y"] = pos_minifix_topo_mm
                    ops_lateral.append(od)

            # 3. Se fundo embutido com rasgo, gera usinagem de canal nas peças da caixa
            if eff_tipo_fundo == "rasgo":
                canal_lateral = make_back_panel_groove(
                    comprimento_mm=(altura_caixa * 1000.0),
                    afastamento_traseiro_mm=recuo_fundo_mm,
                    largura_canal_mm=esp_fundo_mm,
                    profundidade_canal_mm=prof_rasgo_mm,
                    face="traseira",
                )
                ops_lateral.append(canal_lateral.to_dict())

                canal_base = make_back_panel_groove(
                    comprimento_mm=(largura_interna * 1000.0),
                    afastamento_traseiro_mm=recuo_fundo_mm,
                    largura_canal_mm=esp_fundo_mm,
                    profundidade_canal_mm=prof_rasgo_mm,
                    face="traseira",
                )
                ops_base.append(canal_base.to_dict())

                if tipo_topo == "fechado":
                    canal_tampo = make_back_panel_groove(
                        comprimento_mm=(largura_interna * 1000.0),
                        afastamento_traseiro_mm=recuo_fundo_mm,
                        largura_canal_mm=esp_fundo_mm,
                        profundidade_canal_mm=prof_rasgo_mm,
                        face="traseira",
                    )
                    ops_tampo.append(canal_tampo.to_dict())

        # Fechamento superior: Tampo Fechado VS Travessas
        ops_trav_f = []
        ops_trav_t = []
        if tipo_topo != "fechado" and gerar_furacao:
            from ..production.machining import make_stretcher_joint_holes
            larg_trav_f_mm = (LTF * 1000.0) if not travessa_frontal_em_pe else (E_trav * 1000.0)
            larg_trav_t_mm = (LTT * 1000.0) if not travessa_traseira_em_pe else (E_trav * 1000.0)
            compr_trav_mm = largura_interna * 1000.0

            # 1. Usinagens nas próprias travessas (furos de Minifix e Cavilha nas pontas esquerda e direita)
            ops_trav_f = [
                o.to_dict() for o in make_stretcher_joint_holes(
                    largura_travessa_mm=larg_trav_f_mm,
                    esp_travessa_mm=(E_trav * 1000.0),
                    face="traseira",
                    usar_minifix=usar_mini,
                    comprimento_travessa_mm=compr_trav_mm,
                    eh_travessa=True,
                )
            ]
            ops_trav_t = [
                o.to_dict() for o in make_stretcher_joint_holes(
                    largura_travessa_mm=larg_trav_t_mm,
                    esp_travessa_mm=(E_trav * 1000.0),
                    face="traseira",
                    usar_minifix=usar_mini,
                    comprimento_travessa_mm=compr_trav_mm,
                    eh_travessa=True,
                )
            ]

            # 2. Usinagens correspondentes nas laterais da caixa (furação de topo para receber as travessas)
            pos_y_tf = (LTF * 1000.0 / 2.0) if not travessa_frontal_em_pe else (E_trav * 1000.0 / 2.0)
            ops_lateral.append({
                "tipo": "furo",
                "face": "traseira",
                "x": pos_y_tf,
                "y": max(0.0, (altura_caixa * 1000.0) - (esp_mm / 2.0)),
                "diametro": 8.0,
                "profundidade": 12.0,
                "descricao": "Furo Junção Travessa Frontal (Ø8mm)",
            })
            pos_y_tt = max(0.0, (prof_mm) - ((LTT * 1000.0 / 2.0) if not travessa_traseira_em_pe else (E_trav * 1000.0 / 2.0)))
            ops_lateral.append({
                "tipo": "furo",
                "face": "traseira",
                "x": pos_y_tt,
                "y": max(0.0, (altura_caixa * 1000.0) - (esp_mm / 2.0)),
                "diametro": 8.0,
                "profundidade": 12.0,
                "descricao": "Furo Junção Travessa Traseira (Ø8mm)",
            })

        groups = [
            create_board_group(
                f"{prefixo} - Lateral Esquerda", (ox, oy, oz + R), (E, P, altura_caixa), material,
                fita_c1=f_cx_c1, fita_c2=f_cx_c2, fita_l1=f_cx_l1, fita_l2=f_cx_l2, color=cor,
                material_fita=mat_fita_cx, cor_fita=cor_fita_cx, operacoes=ops_lateral,
            ),
            create_board_group(
                f"{prefixo} - Lateral Direita", (ox + L - E, oy, oz + R), (E, P, altura_caixa), material,
                fita_c1=f_cx_c1, fita_c2=f_cx_c2, fita_l1=f_cx_l1, fita_l2=f_cx_l2, color=cor,
                material_fita=mat_fita_cx, cor_fita=cor_fita_cx, operacoes=ops_lateral,
            ),
            create_board_group(
                f"{prefixo} - Base Inferior", (ox + E, oy, oz + R), (largura_interna, P, E), material,
                fita_c1=f_cx_c1, fita_c2=f_cx_c2, fita_l1=f_cx_l1, fita_l2=f_cx_l2, color=cor,
                material_fita=mat_fita_cx, cor_fita=cor_fita_cx, operacoes=ops_base,
            ),
        ]

        if tipo_topo == "fechado":
            groups.append(create_board_group(
                f"{prefixo} - Tampo Superior",
                (ox + E, oy, oz + A - E),
                (largura_interna, P, E),
                material,
                fita_c1=f_cx_c1, fita_c2=f_cx_c2, fita_l1=f_cx_l1, fita_l2=f_cx_l2,
                color=cor, material_fita=mat_fita_cx, cor_fita=cor_fita_cx, operacoes=ops_tampo,
            ))
        else:
            # Material e espessura específicos das travessas (se definidos, caso contrário herda da caixa)
            mat_trav = material_travessas or material
            cor_trav = cls.get_material_color(mat_trav)
            mat_fita_tr = material_fita_travessas or mat_trav
            cor_fita_tr = cls.get_material_color(mat_fita_tr) if material_fita_travessas else None

            # Resolução das fitas de borda das travessas
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
            elif modo_fita == "custom" and isinstance(fita_travessas_faces, dict):
                f_c1_tf = bool(fita_travessas_faces.get("fita_c1", True))
                f_c2_tf = bool(fita_travessas_faces.get("fita_c2", False))
                f_l1_tf = bool(fita_travessas_faces.get("fita_l1", False))
                f_l2_tf = bool(fita_travessas_faces.get("fita_l2", False))
                f_c1_tt = bool(fita_travessas_faces.get("fita_c1_traseira", False))
                f_c2_tt = bool(fita_travessas_faces.get("fita_c2_traseira", False))
                f_l1_tt = bool(fita_travessas_faces.get("fita_l1_traseira", False))
                f_l2_tt = bool(fita_travessas_faces.get("fita_l2_traseira", False))
            else:
                f_c1_tf, f_c2_tf, f_l1_tf, f_l2_tf = True, False, False, False
                f_c1_tt, f_c2_tt, f_l1_tt, f_l2_tt = False, False, False, False

            # Travessa frontal (em pé / vertical ou deitada / horizontal)
            if travessa_frontal_em_pe:
                groups.append(create_board_group(
                    f"{prefixo} - Travessa Frontal Em Pe",
                    (ox + E, oy, oz + A - LTF),
                    (largura_interna, E_trav, LTF),
                    mat_trav, fita_c1=f_c1_tf, fita_c2=f_c2_tf, fita_l1=f_l1_tf, fita_l2=f_l2_tf, color=cor_trav,
                    material_fita=mat_fita_tr, cor_fita=cor_fita_tr, operacoes=ops_trav_f,
                ))
            else:
                groups.append(create_board_group(
                    f"{prefixo} - Travessa Frontal",
                    (ox + E, oy, oz + A - E_trav),
                    (largura_interna, LTF, E_trav),
                    mat_trav, fita_c1=f_c1_tf, fita_c2=f_c2_tf, fita_l1=f_l1_tf, fita_l2=f_l2_tf, color=cor_trav,
                    material_fita=mat_fita_tr, cor_fita=cor_fita_tr, operacoes=ops_trav_f,
                ))

            # Travessa traseira (em pé / vertical ou deitada / horizontal)
            if travessa_traseira_em_pe:
                groups.append(create_board_group(
                    f"{prefixo} - Travessa Traseira Em Pe",
                    (ox + E, oy + P - E_trav, oz + A - LTT),
                    (largura_interna, E_trav, LTT),
                    mat_trav, fita_c1=f_c1_tt, fita_c2=f_c2_tt, fita_l1=f_l1_tt, fita_l2=f_l2_tt, color=cor_trav,
                    material_fita=mat_fita_tr, cor_fita=cor_fita_tr, operacoes=ops_trav_t,
                ))
            else:
                groups.append(create_board_group(
                    f"{prefixo} - Travessa Traseira",
                    (ox + E, oy + P - LTT, oz + A - E_trav),
                    (largura_interna, LTT, E_trav),
                    mat_trav, fita_c1=f_c1_tt, fita_c2=f_c2_tt, fita_l1=f_l1_tt, fita_l2=f_l2_tt, color=cor_trav,
                    material_fita=mat_fita_tr, cor_fita=cor_fita_tr, operacoes=ops_trav_t,
                ))

        # Rodapé Frontal
        if R > 0.01:
            groups.append(create_board_group(
                f"{prefixo} - Rodape Frontal",
                (ox, oy + 0.05, oz),
                (L, E, R),
                material, color=cor
            ))

        # Geração integrada do Fundo (se solicitado)
        fundo_grp = cls.build_fundo_board(
            prefixo=prefixo,
            largura_interna_m=largura_interna,
            altura_interna_m=(altura_caixa - 2 * E),
            largura_total_m=L,
            altura_total_caixa_m=altura_caixa,
            prof_total_m=P,
            esp_lateral_m=E,
            origin_caixa=(ox, oy, oz + R),
            z_interno_base_m=(oz + R + E),
            tipo_fundo=eff_tipo_fundo,
            esp_fundo_mm=esp_fundo_mm,
            recuo_fundo_mm=recuo_fundo_mm,
            prof_rasgo_mm=prof_rasgo_mm,
            folga_fundo_mm=folga_fundo_mm,
            material_fundo=material_fundo,
        )
        if fundo_grp:
            groups.append(fundo_grp)

        info = {
            "ox": ox, "oy": oy, "oz": oz,
            "L": L, "A": A, "P": P, "E": E, "R": R,
            "altura_caixa": altura_caixa,
            "largura_interna": largura_interna,
            "tipo_topo": tipo_topo,
            "LTF": LTF, "LTT": LTT,
            "cor": cor,
            "fundo_grp": fundo_grp,
        }
        return groups, info

    @classmethod
    def build_caixa_inferior(
        cls,
        prefixo: str,
        largura_mm: float,
        altura_mm: float,
        prof_mm: float,
        esp_mm: float = 15.0,
        rodape_mm: float = 100.0,
        material: str = "MDF Branco TX 15mm",
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        larg_travessa_frontal_mm: float = 70.0,
        larg_travessa_traseira_mm: float = 70.0,
        travessa_frontal_em_pe: bool = False,
        travessa_traseira_em_pe: bool = False,
        material_travessas: str | None = None,
        esp_travessas_mm: float | None = None,
        fita_travessas_modo: str = "frontal_1L",
        fita_travessas_faces: dict[str, bool] | None = None,
        fita_caixa_modo: str = "frontal_1L",
        material_fita_caixa: str | None = None,
        material_fita_travessas: str | None = None,
        gerar_furacao: bool = True,
        dispositivo_fixacao: str = "minifix_cavilha",
    ) -> tuple[list[Group], dict]:
        """Wrapper de compatibilidade para módulos inferiores de cozinha com travessas."""
        return cls.build_caixa_modular(
            prefixo=prefixo,
            largura_mm=largura_mm,
            altura_mm=altura_mm,
            prof_mm=prof_mm,
            esp_mm=esp_mm,
            rodape_mm=rodape_mm,
            tipo_topo="travessas",
            material=material,
            offset=offset,
            larg_travessa_frontal_mm=larg_travessa_frontal_mm,
            larg_travessa_traseira_mm=larg_travessa_traseira_mm,
            travessa_frontal_em_pe=travessa_frontal_em_pe,
            travessa_traseira_em_pe=travessa_traseira_em_pe,
            material_travessas=material_travessas,
            esp_travessas_mm=esp_travessas_mm,
            fita_travessas_modo=fita_travessas_modo,
            fita_travessas_faces=fita_travessas_faces,
            material_fita_travessas=material_fita_travessas,
            fita_caixa_modo=fita_caixa_modo,
            material_fita_caixa=material_fita_caixa,
            tem_fundo=False,  # Os módulos chamadores de build_caixa_inferior adicionam o fundo em seguida
            gerar_furacao=gerar_furacao,
            dispositivo_fixacao=dispositivo_fixacao,
        )
