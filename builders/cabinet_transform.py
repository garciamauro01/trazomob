# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Operacoes de transformacao 3D do CabinetBuilder."""
from __future__ import annotations

import logging
import math
from typing import Any

from PySide6.QtGui import QVector3D

from core.group import Group

logger = logging.getLogger("trazomob.cabinet_transform")


class CabinetTransformMixin:
    """Rotacao e redimensionamento parametrico de modulos."""

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
        from ..domain.module_geometry import get_module_carcass_bounds
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
            from ..domain.schema import live_module_data
            mod_p = live_module_data(module_group)
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
        rebuild: bool = True,
    ) -> bool:
        """Escala um módulo do TrazoMob (e todas as suas peças filhas) em torno de ``center``
        e sincroniza automaticamente suas dimensões paramétricas (`largura`, `profundidade`, `altura`)
        e sua âncora (`offset`, `_unrot_carcass_span`) em ``module_group.ext['trazomob_module']``.
        Se ``rebuild=True`` e ``update_param=True``, regenera parametricamente os componentes filhos
        para preservar rigorosamente as espessuras de chapas (MDF 15/18mm) e ferragens sem distorção.
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
            from ..domain.schema import live_module_data
            mod_p = live_module_data(module_group)
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

                # Limitação rígida (Clamp) de marcenaria: não permite que dimensões ultrapassem o limite útil da chapa (2720mm)
                from ..domain.materials_catalog import CHAPA_MAX_COMPRIMENTO_UTIL_MM
                for dim_key in ("largura", "altura", "profundidade"):
                    if dim_key in mod_p and isinstance(mod_p[dim_key], (int, float)):
                        if mod_p[dim_key] > CHAPA_MAX_COMPRIMENTO_UTIL_MM:
                            mod_p[dim_key] = CHAPA_MAX_COMPRIMENTO_UTIL_MM

                from ..domain.module_geometry import get_module_carcass_bounds
                from ..interaction.magnetic_drag import get_module_bounds
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

                    # Se solicitado o rearranjo paramétrico, regenera as peças filhas
                    # mantendo a espessura de chapas de MDF (15/18mm) e ferragens sem distorção.
                    if rebuild:
                        try:
                            cls._rebuild_scaled_module_pieces(module_group, mod_p, b_after)
                        except Exception:
                            logger.debug("Falha ao reconstruir peças do módulo redimensionado", exc_info=True)

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

    @classmethod
    def _rebuild_scaled_module_pieces(
        cls,
        module_group: Group,
        mod_p: dict[str, Any],
        b_after: tuple[float, float, float, float, float, float],
    ) -> None:
        """Regenera in-place as peças componentes de um módulo de marcenaria escalado,
        garantindo espessuras nominais fiéis de MDF (15/18mm) e ferragens sem deformação.
        """
        from ..builders.cabinet import CabinetBuilder
        from ..domain.module_geometry import get_module_carcass_bounds
        from ..interaction.magnetic_drag import get_module_bounds

        params_build = dict(mod_p)
        offset = params_build.get("offset", (0.0, 0.0, 0.0))
        if not isinstance(offset, (list, tuple)) or len(offset) < 3:
            offset = (0.0, 0.0, 0.0)
        offset = tuple(float(v) for v in offset)

        new_mod = CabinetBuilder.build_module_group(params_build, offset=offset)
        if new_mod is None:
            return

        b_new = get_module_carcass_bounds(new_mod) or get_module_bounds(new_mod)
        if b_after and b_new:
            shift = QVector3D(
                b_after[0] - b_new[0],
                b_after[2] - b_new[2],
                b_after[4] - b_new[4],
            )
            if shift.length() > 1e-7:
                targets = getattr(new_mod, "children", []) or [new_mod]
                for t in targets:
                    m_sub = getattr(t, "mesh", None)
                    if m_sub and hasattr(m_sub, "vertices"):
                        for v in m_sub.vertices:
                            v.position += shift
                        m_sub._mut_serial = getattr(m_sub, "_mut_serial", 0) + 1
                    if getattr(t, "ext", None) is not None:
                        if "orig_vertices" in t.ext:
                            t.ext["orig_vertices"] = [orig + shift for orig in t.ext["orig_vertices"]]
                        if "hinge_pivot" in t.ext and isinstance(t.ext["hinge_pivot"], QVector3D):
                            t.ext["hinge_pivot"] += shift

        # Atualiza o grupo mestre in-place com a geometria e peças reconstruídas
        for c in new_mod.children:
            c.owner = module_group
        module_group.children = list(new_mod.children)
        module_group.name = new_mod.name
        if hasattr(new_mod, "mesh") and new_mod.mesh is not None:
            module_group.mesh = new_mod.mesh
        if hasattr(new_mod, "ext") and isinstance(new_mod.ext, dict):
            # Preserva os metadados calculados
            for k, val in new_mod.ext.items():
                if k not in module_group.ext or k in ("trazomob_module", "trazomob_esquadria"):
                    module_group.ext[k] = val

