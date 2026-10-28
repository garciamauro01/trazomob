# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Construtor paramétrico 3D de armários e chapas de MDF (CabinetBuilder)."""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

from PySide6.QtGui import QVector3D

from core.group import Group
from core.mesh import Mesh


from .builder_mesh_utils import (
    _get_material_texture,
    _make_board_mesh,
    _make_box_faces,
    _contorno_retangular_xy,
    _make_slab_with_holes_mesh,
    _make_bowl_mesh,
    _make_gourmet_faucet_mesh,
    _render_machining_holes_in_mesh,
    _get_puxador_rgb,
    _build_perfil_geometry_legacy,
    _build_perfil_geometry,
    _add_handle_geometry,
    create_board_group,
)


from core.history import Command
from .builder_bancadas import BancadaBuilder
from .builder_armarios import ArmarioBuilder
from .builder_aereos_torres import AereoTorreBuilder
from .builder_cantos_especiais import CantoEspecialBuilder
from .builder_balcoes_aereos import BalcaoAereoBuilder


class RotateTrazoMobModuleCommand(Command):
    """Comando reversível (Undo/Redo) para rotação de módulos e peças do TrazoMob."""

    def __init__(
        self,
        module_group: Group,
        degrees: float,
        center: tuple[float, float, float] | QVector3D | None = None,
        axis: tuple[float, float, float] | QVector3D = (0.0, 0.0, 1.0),
        viewport=None,
    ):
        self.module_group = module_group
        self.degrees = float(degrees)
        self.center = center
        self.axis = axis
        self.viewport = viewport

    def do(self, scene) -> None:
        CabinetBuilder.rotate_module(
            self.module_group, self.degrees, center=self.center, axis=self.axis, scene=scene, viewport=self.viewport
        )

    def undo(self, scene) -> None:
        CabinetBuilder.rotate_module(
            self.module_group, -self.degrees, center=self.center, axis=self.axis, scene=scene, viewport=self.viewport
        )


class CabinetBuilder:
    """Gera módulos dinâmicos e suas peças componentes."""

    @classmethod
    def rotate_module(
        cls,
        module_group: Group,
        degrees: float,
        center: tuple[float, float, float] | QVector3D | None = None,
        axis: tuple[float, float, float] | QVector3D = (0.0, 0.0, 1.0),
        scene=None,
        viewport=None,
        update_param: bool = True,
    ) -> bool:
        """Rotaciona um módulo do TrazoMob (e todas as suas peças filhas) pelo ângulo em graus.

        Suporta:
        - Módulo mestre contendo peças em ``module_group.children``.
        - Peça individual com malha direta ``module_group.mesh``.
        - Atualização dos metadados e 'orig_vertices' para preservação da cinemática interativa.
        """
        if module_group is None:
            return False

        from core.history import rotation_matrix, _dirty_group_chunks

        # Converte o eixo para QVector3D
        if isinstance(axis, QVector3D):
            axis_vec = axis
        else:
            axis_vec = QVector3D(*axis)

        # Identifica peças alvo
        children = getattr(module_group, "children", []) or []
        targets = children if children else [module_group]

        # Determina o centro da caixaria (antes de qualquer pivô externo)
        from .module_ribbon import get_module_carcass_bounds
        cb_before = get_module_carcass_bounds(module_group)
        if cb_before is not None:
            carcass_center_before = QVector3D(
                (cb_before[0] + cb_before[1]) * 0.5,
                (cb_before[2] + cb_before[3]) * 0.5,
                (cb_before[4] + cb_before[5]) * 0.5,
            )
        else:
            carcass_center_before = QVector3D(0.0, 0.0, 0.0)

        # Determina o centro de rotação efetivo
        if center is None:
            center_vec = carcass_center_before
        elif isinstance(center, QVector3D):
            center_vec = center
        else:
            center_vec = QVector3D(*center)

        m = rotation_matrix(center_vec, axis_vec, degrees)

        for t in targets:
            mesh = getattr(t, "mesh", None)
            if mesh and hasattr(mesh, "vertices"):
                for v in mesh.vertices:
                    v.position = m.map(v.position)
                mesh._mut_serial = getattr(mesh, "_mut_serial", 0) + 1

            if getattr(t, "ext", None) is not None:
                if "orig_vertices" in t.ext:
                    t.ext["orig_vertices"] = [m.map(orig) for orig in t.ext["orig_vertices"]]
                if "slide_delta" in t.ext and isinstance(t.ext["slide_delta"], QVector3D):
                    t.ext["slide_delta"] = m.mapVector(t.ext["slide_delta"])
                if "hinge_pivot" in t.ext and isinstance(t.ext["hinge_pivot"], QVector3D):
                    t.ext["hinge_pivot"] = m.map(t.ext["hinge_pivot"])

        # Atualiza a rotação acumulada do módulo se solicitado (evita somar duas vezes durante build_module_group)
        if update_param and getattr(module_group, "ext", None) is not None and "trazomob_module" in module_group.ext:
            from PySide6.QtGui import QMatrix4x4
            mod_p = module_group.ext["trazomob_module"]
            ax_norm = axis_vec.normalized()
            is_z_axis = abs(ax_norm.x()) < 1e-4 and abs(ax_norm.y()) < 1e-4 and abs(ax_norm.z()) > 0.5

            if is_z_axis:
                eff_deg_z = degrees if ax_norm.z() >= 0.0 else -degrees
                old_rot = float(mod_p.get("rot_z", 0.0) or 0.0)
                mod_p["rot_z"] = (old_rot + eff_deg_z) % 360.0
                # Se já possuía matriz 3D customizada, compõe a rotação Z nela também
                if "rot_matrix_3d" in mod_p and isinstance(mod_p["rot_matrix_3d"], (list, tuple)) and len(mod_p["rot_matrix_3d"]) == 16:
                    m_prev = QMatrix4x4(*[float(x) for x in mod_p["rot_matrix_3d"]])
                    m_step = rotation_matrix(QVector3D(0.0, 0.0, 0.0), ax_norm, degrees)
                    m_comb = m_step * m_prev
                    mod_p["rot_matrix_3d"] = [float(m_comb(r, c)) for r in range(4) for c in range(4)]
            else:
                # Rotação 3D livre (em X, Y ou eixo arbitrário): preserva a matriz 3D exata!
                if "rot_matrix_3d" in mod_p and isinstance(mod_p["rot_matrix_3d"], (list, tuple)) and len(mod_p["rot_matrix_3d"]) == 16:
                    m_prev = QMatrix4x4(*[float(x) for x in mod_p["rot_matrix_3d"]])
                else:
                    old_rot = float(mod_p.get("rot_z", 0.0) or 0.0)
                    m_prev = rotation_matrix(QVector3D(0.0, 0.0, 0.0), QVector3D(0.0, 0.0, 1.0), old_rot)
                m_step = rotation_matrix(QVector3D(0.0, 0.0, 0.0), ax_norm, degrees)
                m_comb = m_step * m_prev
                mod_p["rot_matrix_3d"] = [float(m_comb(r, c)) for r in range(4) for c in range(4)]

            # Sincroniza o offset base usando o deslocamento real do centro da caixaria (new_center - old_center)
            # e preservando a relação exata com as dimensões não-rotacionadas da peça/módulo!
            new_carcass_center = m.map(carcass_center_before)
            unrot_span = mod_p.get("_unrot_carcass_span")
            if isinstance(unrot_span, (list, tuple)) and len(unrot_span) == 6:
                mod_p["offset"] = (
                    float(new_carcass_center.x()) - float(unrot_span[0]),
                    float(new_carcass_center.y()) - float(unrot_span[1]),
                    float(new_carcass_center.z()) - float(unrot_span[2]),
                )
            else:
                delta_c = new_carcass_center - carcass_center_before
                old_off = mod_p.get("offset", (0.0, 0.0, 0.0))
                if isinstance(old_off, (list, tuple)) and len(old_off) >= 3:
                    mod_p["offset"] = (
                        float(old_off[0]) + float(delta_c.x()),
                        float(old_off[1]) + float(delta_c.y()),
                        float(old_off[2]) + float(delta_c.z()),
                    )

        if scene is not None:
            _dirty_group_chunks(scene)
            scene.version += 1

        if viewport is not None:
            # Invalida os caches do renderer para refletir a rotação imediatamente
            for _cache_name in ("_group_chunks", "_inst_chunks"):
                _cache = getattr(viewport, _cache_name, None)
                if isinstance(_cache, dict):
                    _cache.clear()
            if hasattr(viewport, "_placements_memo"):
                viewport._placements_memo = None
            if hasattr(viewport, "_epoch_same"):
                viewport._epoch_same = None
            viewport.update()

        return True

    @classmethod
    def scale_module(
        cls,
        module_group: Group,
        center: tuple[float, float, float] | QVector3D,
        factor: float | tuple[float, float, float] | list[float],
        axes=None,
        scene=None,
        viewport=None,
        update_param: bool = True,
    ) -> bool:
        """Escala um módulo do TrazoMob (e todas as suas peças filhas) em torno de ``center``
        e sincroniza automaticamente suas dimensões paramétricas (`largura`, `profundidade`, `altura`)
        e sua âncora (`offset`, `_unrot_carcass_span`) em ``module_group.ext['trazomob_module']``.
        """
        if module_group is None:
            return False

        from PySide6.QtGui import QMatrix4x4
        from core.history import scale_matrix, _dirty_group_chunks
        from core.group import _remap_uvws, carry_axes

        center_vec = center if isinstance(center, QVector3D) else QVector3D(*center)
        m = scale_matrix(center_vec, factor, axes)

        children = getattr(module_group, "children", []) or []
        targets = children if children else [module_group]

        for t in targets:
            mesh = getattr(t, "mesh", None)
            if mesh and hasattr(mesh, "vertices"):
                for v in list(mesh.vertices):
                    mesh.move_vertex(v, m.map(v.position) - v.position)
                _remap_uvws(mesh, m)
                mesh._mut_serial = getattr(mesh, "_mut_serial", 0) + 1
            carry_axes(t, m)
            if getattr(t, "ext", None) is not None:
                if "orig_vertices" in t.ext and isinstance(t.ext["orig_vertices"], list):
                    t.ext["orig_vertices"] = [m.map(orig) for orig in t.ext["orig_vertices"] if isinstance(orig, QVector3D)]
                if "slide_delta" in t.ext and isinstance(t.ext["slide_delta"], QVector3D):
                    t.ext["slide_delta"] = m.mapVector(t.ext["slide_delta"])
                if "hinge_pivot" in t.ext and isinstance(t.ext["hinge_pivot"], QVector3D):
                    t.ext["hinge_pivot"] = m.map(t.ext["hinge_pivot"])

        if update_param and getattr(module_group, "ext", None) is not None and "trazomob_module" in module_group.ext:
            mod_p = module_group.ext["trazomob_module"]
            tipo = str(mod_p.get("tipo", ""))
            rot_z = float(mod_p.get("rot_z", 0.0) or 0.0)
            rot_mat_3d = mod_p.get("rot_matrix_3d")

            if isinstance(rot_mat_3d, (list, tuple)) and len(rot_mat_3d) == 16:
                m_rot = QMatrix4x4(*[float(x) for x in rot_mat_3d])
                ex = m_rot.mapVector(QVector3D(1.0, 0.0, 0.0)).normalized()
                ey = m_rot.mapVector(QVector3D(0.0, 1.0, 0.0)).normalized()
                ez = m_rot.mapVector(QVector3D(0.0, 0.0, 1.0)).normalized()
            else:
                rad = math.radians(rot_z)
                ex = QVector3D(math.cos(rad), math.sin(rad), 0.0)
                ey = QVector3D(-math.sin(rad), math.cos(rad), 0.0)
                ez = QVector3D(0.0, 0.0, 1.0)

            s_x = m.mapVector(ex).length()
            s_y = m.mapVector(ey).length()
            s_z = m.mapVector(ez).length()

            if s_x > 1e-6 and s_y > 1e-6 and s_z > 1e-6:
                # Mapeia os fatores de escala locais (s_x, s_y, s_z) para os parâmetros de marcenaria:
                if tipo == "peca_lateral":
                    # Lateral avulsa: X local é espessura (E), Y local é profundidade (P), Z local é altura (A)
                    if abs(s_y - 1.0) > 1e-4 and "profundidade" in mod_p:
                        mod_p["profundidade"] = round(float(mod_p["profundidade"]) * s_y, 2)
                    if abs(s_z - 1.0) > 1e-4 and "altura" in mod_p:
                        mod_p["altura"] = round(float(mod_p["altura"]) * s_z, 2)
                elif tipo in ("peca_porta", "peca_fundo", "peca_travessa_em_pe", "peca_pilar_quina"):
                    # Chapa frontal/vertical em XZ: X local é largura (L), Y local é espessura (E), Z local é altura (A)
                    if abs(s_x - 1.0) > 1e-4 and "largura" in mod_p:
                        mod_p["largura"] = round(float(mod_p["largura"]) * s_x, 2)
                    if abs(s_z - 1.0) > 1e-4 and "altura" in mod_p:
                        mod_p["altura"] = round(float(mod_p["altura"]) * s_z, 2)
                    if abs(s_y - 1.0) > 1e-4 and "profundidade" in mod_p:
                        mod_p["profundidade"] = round(float(mod_p["profundidade"]) * s_y, 2)
                else:
                    # Todos os armários, balcões, bancadas, tampo engrossado, base, prateleira, travessa deitada:
                    # X local é largura (L), Y local é profundidade (P), Z local é altura (A)
                    if abs(s_x - 1.0) > 1e-4 and "largura" in mod_p:
                        mod_p["largura"] = round(float(mod_p["largura"]) * s_x, 2)
                    if abs(s_y - 1.0) > 1e-4 and "profundidade" in mod_p:
                        mod_p["profundidade"] = round(float(mod_p["profundidade"]) * s_y, 2)
                    if abs(s_z - 1.0) > 1e-4 and "altura" in mod_p:
                        mod_p["altura"] = round(float(mod_p["altura"]) * s_z, 2)

                from .module_ribbon import get_module_carcass_bounds
                from .magnetic_drag import get_module_bounds
                b_after = get_module_carcass_bounds(module_group) or get_module_bounds(module_group)
                if b_after is not None:
                    cx_a = (b_after[0] + b_after[1]) * 0.5
                    cy_a = (b_after[2] + b_after[3]) * 0.5
                    cz_a = (b_after[4] + b_after[5]) * 0.5
                    unrot_span = mod_p.get("_unrot_carcass_span")
                    if isinstance(unrot_span, (list, tuple)) and len(unrot_span) == 6:
                        new_span = (
                            float(unrot_span[0]) * s_x,
                            float(unrot_span[1]) * s_y,
                            float(unrot_span[2]) * s_z,
                            float(unrot_span[3]) * s_x,
                            float(unrot_span[4]) * s_y,
                            float(unrot_span[5]) * s_z,
                        )
                        mod_p["_unrot_carcass_span"] = new_span
                        mod_p["offset"] = (
                            float(cx_a - new_span[0]),
                            float(cy_a - new_span[1]),
                            float(cz_a - new_span[2]),
                        )
                    else:
                        L_m = float(mod_p.get("largura", 800.0)) / 1000.0
                        P_m = float(mod_p.get("profundidade", 550.0)) / 1000.0
                        mod_p["offset"] = (
                            float(cx_a - L_m * 0.5),
                            float(cy_a - P_m * 0.5),
                            float(b_after[4]),
                        )

        if scene is not None:
            _dirty_group_chunks(scene)
            scene.version += 1

        if viewport is not None:
            for _cache_name in ("_group_chunks", "_inst_chunks"):
                _cache = getattr(viewport, _cache_name, None)
                if isinstance(_cache, dict):
                    _cache.clear()
            if hasattr(viewport, "_placements_memo"):
                viewport._placements_memo = None
            if hasattr(viewport, "_epoch_same"):
                viewport._epoch_same = None
            viewport.update()

        return True

    @staticmethod
    def get_material_color(material: str) -> tuple[float, float, float]:
        mat_lower = material.lower()
        # Materiais de Marmoraria / Pedras / Metais
        if "sao gabriel" in mat_lower or "preto absoluto" in mat_lower or "granito preto" in mat_lower:
            return (0.12, 0.12, 0.13)
        if "nero" in mat_lower or "marquina" in mat_lower:
            return (0.10, 0.10, 0.11)
        if "pietra" in mat_lower or "grey" in mat_lower:
            return (0.32, 0.33, 0.35)
        if "armani" in mat_lower or "gris" in mat_lower:
            return (0.42, 0.38, 0.35)
        if "siena" in mat_lower or "branco siena" in mat_lower:
            return (0.88, 0.88, 0.86)
        if "calacatta" in mat_lower or "calacata" in mat_lower or "carrara" in mat_lower or "parana" in mat_lower:
            return (0.93, 0.93, 0.94)
        if "quartzo" in mat_lower or "silestone" in mat_lower:
            return (0.95, 0.95, 0.95)
        if "corumba" in mat_lower or "cinza andorinha" in mat_lower:
            return (0.58, 0.58, 0.59)
        if "inox" in mat_lower or "aco" in mat_lower or "aço" in mat_lower:
            return (0.80, 0.82, 0.84)
        if "cuba" in mat_lower:
            return (0.75, 0.77, 0.80)
        # MDF / Marcenaria
        if "autentic" in mat_lower:
            return (198 / 255.0, 165 / 255.0, 127 / 255.0)
        if "ciliegio" in mat_lower or "florenca" in mat_lower:
            return (206 / 255.0, 190 / 255.0, 171 / 255.0)
        if "castanho" in mat_lower:
            return (100 / 255.0, 74 / 255.0, 54 / 255.0)
        if "carvalho" in mat_lower:
            return (203 / 255.0, 175 / 255.0, 142 / 255.0)
        if "freijo" in mat_lower or "madeira" in mat_lower:
            return (0.75, 0.55, 0.35)
        if "grafite" in mat_lower or "preto" in mat_lower or "chumbo" in mat_lower:
            return (0.25, 0.25, 0.25)
        if "cinza" in mat_lower or "titanio" in mat_lower:
            return (0.65, 0.65, 0.65)
        return (0.95, 0.95, 0.93)

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
    def build_module_group(cls, params: dict[str, Any], offset: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> Group:
        tipo = params.get("tipo", "balcao")
        L_mm = params["largura"]
        A_mm = params["altura"]
        P_mm = params["profundidade"]
        esp_mm = params.get("espessura", 15.0)
        rodape_mm = params.get("rodape", 100.0)
        material = params.get("material", "MDF Branco TX 15mm")
        material_frentes = params.get("material_frentes", material)
        esp_frentes_mm = params.get("espessura_frentes", esp_mm)

        # Configurações de Fundo TrazoMob
        tipo_fundo = params.get("tipo_fundo")
        if not tipo_fundo:
            tipo_fundo = "rasgo" if params.get("tem_fundo", True) else "sem_fundo"
        esp_fundo_mm = float(params.get("esp_fundo", 6.0))
        recuo_fundo_mm = float(params.get("recuo_fundo", 15.0))
        prof_rasgo_mm = float(params.get("prof_rasgo", 7.0))
        folga_fundo_mm = float(params.get("folga_fundo", 2.0))

        puxador_tipo = params.get("puxador_tipo", "alca")
        puxador_cor = params.get("puxador_cor", "preto")
        puxador_pos = params.get("puxador_pos", "padrao")
        perfil_modelo = str(params.get("perfil_modelo", "gola")).lower()
        if "desconto_perfil" in params:
            desconto_perfil_mm = float(params["desconto_perfil"])
        else:
            from .perfis import get_profile
            desconto_perfil_mm = float(get_profile(perfil_modelo).get("desconto_mm", 35.0))
        pux_kw = {
            "puxador_tipo": puxador_tipo,
            "puxador_cor": puxador_cor,
            "puxador_pos": puxador_pos,
            "desconto_perfil_mm": desconto_perfil_mm,
            "perfil_modelo": perfil_modelo,
        }

        save_params = dict(params)
        pieces = []
        module_name = ""

        fundo_kwargs = {
            "tipo_fundo": tipo_fundo,
            "esp_fundo_mm": esp_fundo_mm,
            "recuo_fundo_mm": recuo_fundo_mm,
            "prof_rasgo_mm": prof_rasgo_mm,
            "folga_fundo_mm": folga_fundo_mm,
        }

        mat_trav_p = params.get("material_travessas")
        esp_trav_p = params.get("esp_travessas_mm", params.get("espessura_travessas"))
        esp_trav_val = float(esp_trav_p) if (esp_trav_p is not None and float(esp_trav_p) > 0) else None

        mat_fita_cx_p = params.get("material_fita_caixa")
        mat_fita_tr_p = params.get("material_fita_travessas")

        gaveta_kwargs = {
            "tipo_fundo_gaveta": str(params.get("tipo_fundo_gaveta", "rasgo")),
            "folga_corredica_mm": float(params.get("folga_corredica_mm", 26.0)),
            "material_gaveta": params.get("material_gaveta"),
            "esp_gaveta_mm": float(params.get("esp_gaveta_mm", 15.0)),
            "material_fita_gaveta": params.get("material_fita_gaveta"),
            "material_fundo_gaveta": params.get("material_fundo_gaveta"),
            "esp_fundo_gaveta_mm": float(params.get("esp_fundo_gaveta_mm", 6.0)),
        }

        travessas_kwargs = {
            "larg_travessa_frontal_mm": float(params.get("larg_travessa_frontal_mm", params.get("larg_travessa_mm", 70.0))),
            "larg_travessa_traseira_mm": float(params.get("larg_travessa_traseira_mm", 70.0)),
            "travessa_frontal_em_pe": bool(params.get("travessa_frontal_em_pe", (tipo == "balcao_pia"))),
            "travessa_traseira_em_pe": bool(params.get("travessa_traseira_em_pe", False)),
            "recuo_porta_topo_mm": float(params.get("recuo_porta_topo_mm", params.get("recuo_porta_pia_mm", 50.0))),
            "material_travessas": mat_trav_p,
            "esp_travessas_mm": esp_trav_val,
            "fita_travessas_modo": str(params.get("fita_travessas_modo", "frontal_1L")),
            "fita_travessas_faces": params.get("fita_travessas_faces"),
            "fita_caixa_modo": str(params.get("fita_caixa_modo", "frontal_1L")),
            "material_fita_caixa": mat_fita_cx_p,
            "material_fita_travessas": mat_fita_tr_p,
            "gerar_furacao": bool(params.get("gerar_furacao", True)),
            "dispositivo_fixacao": str(params.get("dispositivo_fixacao", "minifix_cavilha")),
        }

        if tipo == "balcao":
            module_name = f"Balcao {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_balcao(
                L_mm, A_mm, P_mm, esp_mm=esp_mm, rodape_mm=rodape_mm,
                num_portas=params.get("num_portas", 2),
                num_prateleiras=params.get("num_prateleiras", 1),
                num_divisoes=params.get("num_divisoes"),
                tem_fundo=(tipo_fundo != "sem_fundo"),
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw, **travessas_kwargs
            )
        elif tipo == "gaveteiro":
            module_name = f"Gaveteiro {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_gaveteiro(
                L_mm, A_mm, P_mm, num_gavetas=params.get("num_gavetas", 4),
                esp_mm=esp_mm, rodape_mm=rodape_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw, **travessas_kwargs, **gaveta_kwargs
            )
        elif tipo == "balcao_misto":
            module_name = f"Balcao Misto {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_balcao_misto(
                L_mm, A_mm, P_mm,
                num_gavetas=params.get("num_gavetas", 4),
                largura_gaveteiro_mm=params.get("largura_gaveteiro", 450.0),
                num_portas=params.get("num_portas", 2),
                num_prateleiras=params.get("num_prateleiras", 1),
                esp_mm=esp_mm, rodape_mm=rodape_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw, **travessas_kwargs, **gaveta_kwargs
            )
        elif tipo == "balcao_pia":
            module_name = f"Balcao Pia {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_balcao_pia(
                L_mm, A_mm, P_mm, esp_mm=esp_mm, rodape_mm=rodape_mm,
                num_portas=params.get("num_portas", 2),
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                tem_fundo=(tipo_fundo != "sem_fundo"),
                offset=offset, **fundo_kwargs, **pux_kw, **travessas_kwargs
            )
        elif tipo == "balcao_canto":
            module_name = f"Canto Reto {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_canto_reto(
                L_mm, A_mm, P_mm, esp_mm=esp_mm, rodape_mm=rodape_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw, **travessas_kwargs
            )
        elif tipo in ("balcao_canto_l", "canto_l"):
            module_name = f"Canto L {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_canto_l(
                L_mm, A_mm, P_mm, larg_asa_mm=params.get("larg_asa", 550.0),
                esp_mm=esp_mm, rodape_mm=rodape_mm,
                num_prateleiras=params.get("num_prateleiras", 1),
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw, **travessas_kwargs
            )
        elif tipo == "porta_tempero":
            module_name = f"Porta-Tempero {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_porta_tempero(
                L_mm, A_mm, P_mm, esp_mm=esp_mm, rodape_mm=rodape_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **pux_kw, **travessas_kwargs
            )
        elif tipo == "balcao_forno":
            module_name = f"Balcao Forno {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_balcao_forno(
                L_mm, A_mm, P_mm, esp_mm=esp_mm, rodape_mm=rodape_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset,
                tem_gaveta=bool(params.get("tem_gaveta", True)),
                alt_gaveta_mm=float(params.get("alt_gaveta_mm", 150.0)),
                **pux_kw, **travessas_kwargs, **gaveta_kwargs
            )
        elif tipo == "aereo":
            module_name = f"Aereo {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_aereo(
                L_mm, A_mm, P_mm, esp_mm=esp_mm,
                num_portas=params.get("num_portas", 2),
                num_prateleiras=params.get("num_prateleiras", 1),
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw
            )
        elif tipo == "aereo_basculante":
            module_name = f"Aereo Basculante {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_aereo_basculante(
                L_mm, A_mm, P_mm, esp_mm=esp_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw
            )
        elif tipo == "aereo_basculante_duplo":
            module_name = f"Aereo Basc Duplo {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_aereo_basculante_duplo(
                L_mm, A_mm, P_mm, esp_mm=esp_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw
            )
        elif tipo == "aereo_microondas":
            module_name = f"Aereo Microondas {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_aereo_microondas(
                L_mm, A_mm, P_mm, esp_mm=esp_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset,
                tipo_porta_superior=params.get("tipo_porta_superior", "basculante"),
                num_portas=int(params.get("num_portas", 1)),
                **fundo_kwargs, **pux_kw
            )
        elif tipo == "torre_quente":
            module_name = f"Torre Quente {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_torre_quente(
                L_mm, A_mm, P_mm, esp_mm=esp_mm, rodape_mm=rodape_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw, **gaveta_kwargs
            )
        elif tipo == "caixa_geladeira":
            module_name = f"Torre Geladeira {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_caixa_geladeira(
                L_mm, A_mm, P_mm, esp_mm=esp_mm,
                alt_nicho_geladeira_mm=float(params.get("alt_nicho_geladeira_mm", 1800.0)),
                num_portas=int(params.get("num_portas", 2)),
                tipo_porta_superior=str(params.get("tipo_porta_superior", "duas_portas")),
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw
            )
        elif tipo in ("roupeiro", "armario_1p_cabide"):
            module_name = f"Roupeiro {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            n_portas = int(params.get("num_portas", 1 if tipo == "armario_1p_cabide" else 2))
            save_params["num_portas"] = n_portas
            pieces = cls.build_roupeiro_cabideiro(
                L_mm, A_mm, P_mm, num_portas=n_portas, esp_mm=esp_mm, rodape_mm=rodape_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw
            )
        elif tipo in ("roupeiro_correr", "roupeiro_correr_2p", "roupeiro_correr_3p"):
            n_vaos = int(params.get("num_vaos", 3 if tipo == "roupeiro_correr_3p" or int(params.get("num_portas", 2)) == 3 else 2))
            save_params["num_vaos"] = n_vaos
            save_params["num_portas"] = n_vaos
            exibir_portas = bool(params.get("exibir_portas", params.get("has_portas", True)))
            save_params["exibir_portas"] = exibir_portas
            module_name = f"Roupeiro {n_vaos} V?os Correr {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_roupeiro_portas_correr(
                L_mm, A_mm, P_mm, num_portas=n_vaos, num_vaos=n_vaos,
                esp_mm=esp_mm, rodape_mm=rodape_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, exibir_portas=exibir_portas, **fundo_kwargs, **pux_kw
            )
        elif tipo in ("armario_prateleiras", "armario_1p_prat", "armario_2p_prat"):
            n_portas = int(params.get("num_portas", 1 if tipo == "armario_1p_prat" else 2))
            save_params["num_portas"] = n_portas
            n_prat = params.get("num_prateleiras", 5 if n_portas == 1 else 4)
            module_name = f"Armário {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_armario_prateleiras(
                L_mm, A_mm, P_mm, num_portas=n_portas, num_prateleiras=n_prat,
                esp_mm=esp_mm, rodape_mm=rodape_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw
            )
        elif tipo == "armario_2p_divisao":
            module_name = f"Armário 2P Divisão {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_armario_divisoria(
                L_mm, A_mm, P_mm, num_prateleiras=params.get("num_prateleiras", 4),
                esp_mm=esp_mm, rodape_mm=rodape_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw
            )
        elif tipo == "armario_3p_divisao":
            module_name = f"Armário 3P {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_armario_3portas(
                L_mm, A_mm, P_mm, num_gavetas=params.get("num_gavetas", 2),
                esp_mm=esp_mm, rodape_mm=rodape_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw
            )
        elif tipo == "gabinete_banheiro":
            module_name = f"Gabinete Banheiro {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_gabinete_banheiro(
                L_mm, A_mm, P_mm, esp_mm=esp_mm,
                material=material, material_frentes=material_frentes, esp_frentes_mm=esp_frentes_mm,
                offset=offset, **fundo_kwargs, **pux_kw, **gaveta_kwargs
            )
        elif tipo == "nicho":
            module_name = f"Nicho {int(L_mm)}x{int(A_mm)}x{int(P_mm)}"
            pieces = cls.build_nicho(
                L_mm, A_mm, P_mm, esp_mm=esp_mm,
                divisoes_vert=params.get("divisoes_vert", 0),
                divisoes_horiz=params.get("divisoes_horiz", 1),
                material=material, offset=offset
            )
        elif tipo == "bancada_reta":
            module_name = f"Bancada Pedra {int(L_mm)}x{int(P_mm)}"
            pieces = cls.build_bancada_reta(
                L_mm, altura_mm=A_mm, prof_mm=P_mm,
                esp_pedra_mm=float(params.get("esp_pedra", 20.0)),
                altura_saia_mm=float(params.get("altura_saia", 40.0)),
                altura_frontao_mm=float(params.get("altura_frontao", 100.0)),
                balanco_frontal_mm=float(params.get("balanco_frontal", 20.0)),
                tem_frontao_traseiro=bool(params.get("tem_frontao_traseiro", True)),
                tem_frontao_esq=bool(params.get("tem_frontao_esq", False)),
                tem_frontao_dir=bool(params.get("tem_frontao_dir", False)),
                tem_saia_esq=bool(params.get("tem_saia_esq", True)),
                tem_saia_dir=bool(params.get("tem_saia_dir", True)),
                material=material, offset=offset
            )
        elif tipo == "bancada_pia":
            module_name = f"Bancada Pia {int(L_mm)}x{int(P_mm)}"
            pieces = cls.build_bancada_pia(
                L_mm, altura_mm=A_mm, prof_mm=P_mm,
                esp_pedra_mm=float(params.get("esp_pedra", 20.0)),
                altura_saia_mm=float(params.get("altura_saia", 40.0)),
                altura_frontao_mm=float(params.get("altura_frontao", 100.0)),
                balanco_frontal_mm=float(params.get("balanco_frontal", 20.0)),
                tem_saia_esq=bool(params.get("tem_saia_esq", True)),
                tem_saia_dir=bool(params.get("tem_saia_dir", True)),
                largura_cuba_mm=float(params.get("largura_cuba", 560.0)),
                prof_cuba_mm=float(params.get("prof_cuba", 400.0)),
                profundidade_cuba_mm=float(params.get("profundidade_cuba", 180.0)),
                posicao_cuba=str(params.get("posicao_cuba", "centro")),
                tipo_cuba=str(params.get("tipo_cuba", "inox_simples")),
                canto_recorte=str(params.get("canto_recorte", "arredondado")),
                raio_canto_mm=float(params.get("raio_canto_mm", 20.0)),
                tem_area_molhada=bool(params.get("tem_area_molhada", True)),
                rebaixo_molhado_mm=float(params.get("rebaixo_molhado_mm", 3.0)),
                tem_torneira=bool(params.get("tem_torneira", True)),
                material=material, offset=offset
            )
        elif tipo in ("bancada_canto_l", "bancada_canto"):
            module_name = f"Bancada L {int(L_mm)}x{int(P_mm)}"
            pieces = cls.build_bancada_canto_l(
                L_mm, altura_mm=A_mm, prof_mm=P_mm,
                larg_asa_mm=float(params.get("larg_asa", 600.0)),
                esp_pedra_mm=float(params.get("esp_pedra", 20.0)),
                altura_saia_mm=float(params.get("altura_saia", 40.0)),
                altura_frontao_mm=float(params.get("altura_frontao", 100.0)),
                tem_saia_esq=bool(params.get("tem_saia_esq", True)),
                tem_saia_dir=bool(params.get("tem_saia_dir", True)),
                material=material, offset=offset
            )
        elif tipo == "bancada_ilha":
            module_name = f"Ilha Gourmet {int(L_mm)}x{int(P_mm)}"
            pieces = cls.build_bancada_ilha(
                L_mm, altura_mm=A_mm, prof_mm=P_mm,
                esp_pedra_mm=float(params.get("esp_pedra", 20.0)),
                altura_saia_mm=float(params.get("altura_saia", 60.0)),
                material=material, offset=offset
            )
        elif tipo == "peca_lateral":
            module_name = f"Lateral {int(P_mm)}x{int(A_mm)}"
            pieces = cls.build_peca_avulsa(
                "lateral", L_mm, A_mm, P_mm, esp_mm=esp_mm, material=material,
                offset=offset, material_fita=mat_fita_cx_p
            )
        elif tipo == "peca_base":
            module_name = f"Base/Tampo {int(L_mm)}x{int(P_mm)}"
            pieces = cls.build_peca_avulsa(
                "base", L_mm, A_mm, P_mm, esp_mm=esp_mm, material=material,
                offset=offset, material_fita=mat_fita_cx_p
            )
        elif tipo == "peca_tampo_engrossado":
            module_name = f"Tampo Engrossado {int(L_mm)}x{int(P_mm)}x{int(A_mm)}"
            esp_ch = float(params.get("esp_chapa", esp_mm if esp_mm > 0 else 18.0))
            larg_eng = float(params.get("larg_engrosso", 70.0))
            tipo_eng = str(params.get("tipo_engrosso", "3_lados"))
            qtd_eng = int(params.get("qtd_engrosso", 1))
            fechar_emb = bool(params.get("fechar_embaixo", False))
            pieces = cls.build_tampo_engrossado(
                L_mm, A_mm, P_mm,
                esp_chapa_mm=esp_ch,
                larg_engrosso_mm=larg_eng,
                tipo_engrosso=tipo_eng,
                qtd_engrosso=qtd_eng,
                fechar_embaixo=fechar_emb,
                material=material,
                material_fita=mat_fita_cx_p,
                offset=offset,
            )
        elif tipo == "peca_prateleira":
            module_name = f"Prateleira {int(L_mm)}x{int(P_mm)}"
            pieces = cls.build_peca_avulsa(
                "prateleira", L_mm, A_mm, P_mm, esp_mm=esp_mm, material=material,
                offset=offset, material_fita=mat_fita_cx_p
            )
        elif tipo == "peca_travessa_deitada":
            module_name = f"Travessa Deitada {int(L_mm)}x{int(P_mm)}"
            pieces = cls.build_peca_avulsa(
                "travessa_deitada", L_mm, A_mm, P_mm, esp_mm=esp_mm, material=material,
                offset=offset, material_fita=mat_fita_cx_p
            )
        elif tipo == "peca_travessa_em_pe":
            module_name = f"Travessa em Pé {int(L_mm)}x{int(A_mm)}"
            pieces = cls.build_peca_avulsa(
                "travessa_em_pe", L_mm, A_mm, P_mm, esp_mm=esp_mm, material=material,
                offset=offset, material_fita=mat_fita_cx_p
            )
        elif tipo == "peca_pilar_quina":
            module_name = f"Pilar Quina {int(L_mm)}x{int(A_mm)}"
            pieces = cls.build_peca_avulsa(
                "pilar_quina", L_mm, A_mm, P_mm, esp_mm=esp_mm, material=material,
                offset=offset, material_fita=mat_fita_cx_p
            )
        elif tipo == "peca_fundo":
            module_name = f"Fundo {int(L_mm)}x{int(A_mm)}"
            pieces = cls.build_peca_avulsa(
                "fundo", L_mm, A_mm, P_mm, esp_mm=esp_mm, material=material,
                offset=offset, material_fita=mat_fita_cx_p
            )
        elif tipo == "peca_porta":
            module_name = f"Porta/Frente {int(L_mm)}x{int(A_mm)}"
            pieces = cls.build_peca_avulsa(
                "porta", L_mm, A_mm, P_mm, esp_mm=esp_mm, material=material_frentes or material,
                offset=offset, material_fita=mat_fita_cx_p, **pux_kw
            )
        elif any(str(tipo).startswith(prefix) for prefix in ("porta_", "janela_")):
            from .builder_esquadrias import EsquadriaBuilder
            r_z = float(params.get("rot_z", params.get("rotacao", 0.0)) or 0.0)
            peit = float(params.get("peitoril_mm", params.get("peitoril", 0.0)) or 0.0)
            return EsquadriaBuilder.load_esquadria_igz(
                item_id=str(tipo),
                largura_mm=L_mm,
                altura_mm=A_mm,
                esp_parede_mm=P_mm,
                peitoril_mm=peit,
                offset=offset,
                rot_z=r_z,
            )
        elif "janela_maximar" in str(tipo):
            from .builder_esquadrias import EsquadriaBuilder
            r_z = float(params.get("rot_z", params.get("rotacao", 0.0)) or 0.0)
            peit = float(params.get("peitoril_mm", 1600.0))
            return EsquadriaBuilder.build_janela_maximar(
                largura_mm=L_mm,
                altura_mm=A_mm,
                esp_parede_mm=P_mm,
                peitoril_mm=peit,
                offset=offset,
                rot_z=r_z,
            )


        # Módulo Mestre (Container)
        master = Group(Mesh(), name=module_name)
        from PySide6.QtGui import QMatrix4x4
        master.xform = QMatrix4x4()
        if "bancada" in str(tipo):
            mod_layer = "Bancadas"
        else:
            mod_layer = "PLANEJADOS"

        master.layer = mod_layer
        for p in pieces:
            p.layer = mod_layer

        if getattr(master, "children", None) is not None:
            master.children.extend(pieces)

        if getattr(master, "ext", None) is None:
            master.ext = {}
        
        # Guarda parâmetros dinâmicos para reedição posterior
        save_params["offset"] = offset
        save_params["material_frentes"] = material_frentes
        save_params["espessura_frentes"] = esp_frentes_mm
        save_params["tipo_fundo"] = tipo_fundo
        save_params["esp_fundo"] = esp_fundo_mm
        save_params["recuo_fundo"] = recuo_fundo_mm
        save_params["prof_rasgo"] = prof_rasgo_mm
        save_params["folga_fundo"] = folga_fundo_mm
        save_params["puxador_tipo"] = puxador_tipo
        save_params["puxador_cor"] = puxador_cor
        save_params["puxador_pos"] = puxador_pos
        save_params["desconto_perfil"] = desconto_perfil_mm
        save_params["perfil_modelo"] = perfil_modelo
        from .entity import set_trazomob
        set_trazomob(master, "module", save_params)

        # Registra a relação exata do centro não-rotacionado com o offset para reconstruções perfeitas
        from .module_ribbon import get_module_carcass_bounds
        cb_unrot = get_module_carcass_bounds(master)
        if cb_unrot is not None:
            cx_u = (cb_unrot[0] + cb_unrot[1]) * 0.5
            cy_u = (cb_unrot[2] + cb_unrot[3]) * 0.5
            cz_u = (cb_unrot[4] + cb_unrot[5]) * 0.5
            save_params["_unrot_carcass_span"] = (
                float(cx_u - offset[0]),
                float(cy_u - offset[1]),
                float(cz_u - offset[2]),
                float(cb_unrot[1] - cb_unrot[0]),
                float(cb_unrot[3] - cb_unrot[2]),
                float(cb_unrot[5] - cb_unrot[4]),
            )

        # Se houver rotação 3D livre (rot_matrix_3d) ou rotação em Z solicitada nos parâmetros
        rot_z = float(params.get("rot_z", params.get("rotacao", 0.0)) or 0.0) % 360.0
        save_params["rot_z"] = rot_z
        rot_mat_3d = params.get("rot_matrix_3d")
        if isinstance(rot_mat_3d, (list, tuple)) and len(rot_mat_3d) == 16:
            save_params["rot_matrix_3d"] = [float(x) for x in rot_mat_3d]
            if cb_unrot is not None:
                c_vec = QVector3D(
                    (cb_unrot[0] + cb_unrot[1]) * 0.5,
                    (cb_unrot[2] + cb_unrot[3]) * 0.5,
                    (cb_unrot[4] + cb_unrot[5]) * 0.5,
                )
            else:
                c_vec = QVector3D(float(offset[0]), float(offset[1]), float(offset[2]))
            m_pure = QMatrix4x4(*save_params["rot_matrix_3d"])
            t_out = QMatrix4x4()
            t_out.translate(c_vec)
            t_in = QMatrix4x4()
            t_in.translate(-c_vec)
            m_full = t_out * m_pure * t_in
            targets = getattr(master, "children", []) or [master]
            for t in targets:
                mesh = getattr(t, "mesh", None)
                if mesh and hasattr(mesh, "vertices"):
                    for v in mesh.vertices:
                        v.position = m_full.map(v.position)
                    mesh._mut_serial = getattr(mesh, "_mut_serial", 0) + 1
                if getattr(t, "ext", None) is not None:
                    if "orig_vertices" in t.ext:
                        t.ext["orig_vertices"] = [m_full.map(orig) for orig in t.ext["orig_vertices"]]
                    if "slide_delta" in t.ext and isinstance(t.ext["slide_delta"], QVector3D):
                        t.ext["slide_delta"] = m_full.mapVector(t.ext["slide_delta"])
                    if "hinge_pivot" in t.ext and isinstance(t.ext["hinge_pivot"], QVector3D):
                        t.ext["hinge_pivot"] = m_full.map(t.ext["hinge_pivot"])
        elif abs(rot_z) > 1e-4:
            cls.rotate_module(master, rot_z, center=None, update_param=False)

        return master

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
            from .machining import make_cabinet_joint_holes, make_back_panel_groove
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
                ops_lateral.extend([
                    o.to_dict() for o in make_cabinet_joint_holes(
                        comprimento_junta_mm=prof_mm,
                        posicao_borda_mm=max(0.0, (altura_caixa * 1000.0) - (esp_mm / 2.0)),
                        face="traseira",
                        usar_minifix=usar_mini,
                    )
                ])

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
            from .machining import make_stretcher_joint_holes
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

    @classmethod
    def build_balcao(cls, *args, **kwargs) -> list[Group]:
        return BalcaoAereoBuilder.build_balcao(*args, **kwargs)

    @classmethod
    def build_gaveteiro(cls, *args, **kwargs) -> list[Group]:
        return BalcaoAereoBuilder.build_gaveteiro(*args, **kwargs)

    @classmethod
    def build_balcao_misto(cls, *args, **kwargs) -> list[Group]:
        return BalcaoAereoBuilder.build_balcao_misto(*args, **kwargs)

    @classmethod
    def build_aereo(cls, *args, **kwargs) -> list[Group]:
        return BalcaoAereoBuilder.build_aereo(*args, **kwargs)

    @classmethod
    def build_nicho(cls, *args, **kwargs) -> list[Group]:
        return BalcaoAereoBuilder.build_nicho(*args, **kwargs)

    @classmethod
    def build_balcao_pia(cls, *args, **kwargs) -> list[Group]:
        return BalcaoAereoBuilder.build_balcao_pia(*args, **kwargs)

    @classmethod
    def build_canto_reto(cls, *args, **kwargs) -> list[Group]:
        return CantoEspecialBuilder.build_canto_reto(*args, **kwargs)

    @classmethod
    def build_canto_l(cls, *args, **kwargs) -> list[Group]:
        return CantoEspecialBuilder.build_canto_l(*args, **kwargs)

    @classmethod
    def build_porta_tempero(cls, *args, **kwargs) -> list[Group]:
        return CantoEspecialBuilder.build_porta_tempero(*args, **kwargs)

    @classmethod
    def build_balcao_forno(cls, *args, **kwargs) -> list[Group]:
        return CantoEspecialBuilder.build_balcao_forno(*args, **kwargs)

    @classmethod
    def build_aereo_basculante(cls, *args, **kwargs) -> list[Group]:
        """Gera aéreo basculante (delegado para AereoTorreBuilder)."""
        return AereoTorreBuilder.build_aereo_basculante(*args, **kwargs)

    @classmethod
    def build_aereo_basculante_duplo(cls, *args, **kwargs) -> list[Group]:
        """Gera aéreo basculante duplo (delegado para AereoTorreBuilder)."""
        return AereoTorreBuilder.build_aereo_basculante_duplo(*args, **kwargs)

    @classmethod
    def build_aereo_microondas(cls, *args, **kwargs) -> list[Group]:
        """Gera aéreo para microondas (delegado para AereoTorreBuilder)."""
        return AereoTorreBuilder.build_aereo_microondas(*args, **kwargs)

    @classmethod
    def build_torre_quente(cls, *args, **kwargs) -> list[Group]:
        """Gera torre quente para fornos e gavetas (delegado para AereoTorreBuilder)."""
        return AereoTorreBuilder.build_torre_quente(*args, **kwargs)

    @classmethod
    def build_caixa_geladeira(cls, *args, **kwargs) -> list[Group]:
        """Gera caixa/fechamento para geladeira com maleiro (delegado para AereoTorreBuilder)."""
        return AereoTorreBuilder.build_caixa_geladeira(*args, **kwargs)

    @classmethod
    def build_roupeiro_portas_correr(cls, *args, **kwargs) -> list[Group]:
        """Gera roupeiro de portas de correr (delegado para ArmarioBuilder)."""
        return ArmarioBuilder.build_roupeiro_portas_correr(*args, **kwargs)

    @classmethod
    def build_roupeiro_cabideiro(cls, *args, **kwargs) -> list[Group]:
        """Gera roupeiro com cabideiro e maleiro (delegado para ArmarioBuilder)."""
        return ArmarioBuilder.build_roupeiro_cabideiro(*args, **kwargs)

    @classmethod
    def build_armario_prateleiras(cls, *args, **kwargs) -> list[Group]:
        """Gera armário com prateleiras e divisórias (delegado para ArmarioBuilder)."""
        return ArmarioBuilder.build_armario_prateleiras(*args, **kwargs)

    @classmethod
    def build_armario_divisoria(cls, *args, **kwargs) -> list[Group]:
        """Gera armário 2 portas com divisória central (delegado para ArmarioBuilder)."""
        return ArmarioBuilder.build_armario_divisoria(*args, **kwargs)

    @classmethod
    def build_armario_3portas(cls, *args, **kwargs) -> list[Group]:
        """Gera armário 3 portas com divisórias internas (delegado para ArmarioBuilder)."""
        return ArmarioBuilder.build_armario_3portas(*args, **kwargs)

    @classmethod
    @classmethod
    def build_gabinete_banheiro(cls, *args, **kwargs) -> list[Group]:
        return BalcaoAereoBuilder.build_gabinete_banheiro(*args, **kwargs)

    @classmethod
    def build_bancada_reta(cls, *args, **kwargs) -> list[Group]:
        """Gera uma bancada reta de pedra (delegado para BancadaBuilder)."""
        return BancadaBuilder.build_bancada_reta(*args, **kwargs)

    @classmethod
    def build_bancada_pia(cls, *args, **kwargs) -> list[Group]:
        """Gera uma bancada de pia com cuba (delegado para BancadaBuilder)."""
        return BancadaBuilder.build_bancada_pia(*args, **kwargs)

    @classmethod
    def build_bancada_canto_l(cls, *args, **kwargs) -> list[Group]:
        """Gera uma bancada em L contínua de pedra (delegado para BancadaBuilder)."""
        return BancadaBuilder.build_bancada_canto_l(*args, **kwargs)

    @classmethod
    def build_bancada_ilha(cls, *args, **kwargs) -> list[Group]:
        """Gera uma ilha / bancada gourmet 360° (delegado para BancadaBuilder)."""
        return BancadaBuilder.build_bancada_ilha(*args, **kwargs)

    @classmethod
    def build_peca_avulsa(cls, *args, **kwargs) -> list[Group]:
        from .builder_parts import CustomPartsBuilder
        return CustomPartsBuilder.build_peca_avulsa(*args, **kwargs)

    @classmethod
    def build_tampo_engrossado(cls, *args, **kwargs) -> list[Group]:
        from .builder_parts import CustomPartsBuilder
        return CustomPartsBuilder.build_tampo_engrossado(*args, **kwargs)
