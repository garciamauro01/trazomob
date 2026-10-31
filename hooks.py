# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors and Pair Programmer.
"""Hooks dinâmicos em tempo de execução para integrar o TrazoMob ao IngeTrazo.

Este módulo desacopla completamente o TrazoMob do código-fonte do core do IngeTrazo:
1. Intercepta a ferramenta de Escalar (ScaleTool) para manter o suporte paramétrico sem distorcer chapas.
2. Intercepta o snap de réguas de montagem na ferramenta de Escalar.
3. Intercepta a ferramenta Mover (MoveTool) para respeitar o cadeado de parede trancada (motion_locked).
4. Intercepta os comandos de histórico (RotateGroupCommand, ScaleGroupCommand, TranslateGroupCommand)
   para regenerar a malha paramétrica nos desfazeres/refazeres (Undo/Redo).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("trazomob.hooks")

_HOOKS_APPLIED = False


def apply_runtime_hooks() -> None:
    """Instala os interceptadores em runtime sem alterar os arquivos do IngeTrazo."""
    global _HOOKS_APPLIED
    if _HOOKS_APPLIED:
        return
    _HOOKS_APPLIED = True

    _patch_move_tool()
    _patch_scale_tool()
    _patch_history_commands()
    _patch_group_copy()
    _patch_render_blender_lights()


def _patch_render_blender_lights() -> None:
    """Estende core.render_blender para aceitar 'led_strip' em LIGHT_KINDS e preservar p1, p2, target."""
    try:
        import core.render_blender as rb
        if "led_strip" not in rb.LIGHT_KINDS:
            rb.LIGHT_KINDS = (*rb.LIGHT_KINDS, "led_strip")
        if "led_strip" not in rb.DEFAULT_POWER:
            rb.DEFAULT_POWER["led_strip"] = 350.0

        orig_clean_lights = rb.clean_lights

        def hooked_clean_lights(raw):
            cleaned = orig_clean_lights(raw)
            # Reintegra campos adicionais do TrazoMob (target, p1, p2, length) se existirem no raw
            raw_list = raw if isinstance(raw, list) else []
            # Mapeia por índice ou posição
            for i, lt in enumerate(cleaned):
                if i < len(raw_list) and isinstance(raw_list[i], dict):
                    src = raw_list[i]
                    for k in ("target", "p1", "p2", "length", "profile_w"):
                        if k in src and k not in lt:
                            lt[k] = src[k]
                    if src.get("kind") == "led_strip":
                        lt["kind"] = "led_strip"
            return cleaned

        rb.clean_lights = hooked_clean_lights
    except Exception as e:
        logger.debug("Não foi possível plugar hook em core.render_blender: %s", e)



def _is_trazomob_module(group: Any) -> bool:
    if group is None:
        return False
    ext = getattr(group, "ext", None)
    if not isinstance(ext, dict):
        return False
    return "trazomob_module" in ext or "corte_cloud_module" in ext or "hellomob_module" in ext


def _get_module_key(group: Any) -> str:
    ext = getattr(group, "ext", {})
    if "trazomob_module" in ext:
        return "trazomob_module"
    if "corte_cloud_module" in ext:
        return "corte_cloud_module"
    return "hellomob_module"


def _unshare_trazomob_module_meshes(group: Any) -> None:
    """Garante que todas as peças filhas de um módulo TrazoMob copiado
    tenham malhas (Mesh) e instâncias próprias e independentes,
    evitando que rotacionar/editar uma cópia afete o módulo original.
    """
    from core.group import transformed_mesh
    from PySide6.QtGui import QMatrix4x4

    def _walk(node):
        for c in getattr(node, "children", []) or []:
            if getattr(c, "mesh", None) is not None:
                c.mesh = transformed_mesh(c.mesh, QMatrix4x4())
            _walk(c)

    _walk(group)


def _patch_group_copy() -> None:
    """Intercepta copy_group em core.group e tools para que módulos TrazoMob
    copiados via Ctrl+Move, Ctrl+C / Ctrl+V ou Rotate sejam 100% independentes.
    """
    try:
        import core.group as grp_mod
        orig_copy_group = grp_mod.copy_group

        def hooked_copy_group(group, delta=None, _in_definition=False):
            new_grp = orig_copy_group(group, delta=delta, _in_definition=_in_definition)
            if _is_trazomob_module(new_grp):
                _unshare_trazomob_module_meshes(new_grp)
            return new_grp

        grp_mod.copy_group = hooked_copy_group

        # Também atualiza nos módulos de tools que importaram copy_group por nome
        for mod_name in ("tools.move", "tools.rotate", "tools.paste", "tools.flip"):
            try:
                import sys
                if mod_name in sys.modules:
                    setattr(sys.modules[mod_name], "copy_group", hooked_copy_group)
            except Exception:
                logger.debug("hook de copy_group não aplicado em %s", mod_name)

    except Exception as e:
        logger.debug("Não foi possível plugar hook em core.group.copy_group: %s", e)


def _patch_move_tool() -> None:
    try:
        import tools.move as move_mod
        orig_is_locked = getattr(move_mod, "_is_locked", None)
        if orig_is_locked is not None:
            def hooked_is_locked(group):
                ext = getattr(group, "ext", None)
                if isinstance(ext, dict):
                    if ext.get("motion_locked"):
                        return True
                    if ("trazomob_wall" in ext or "corte_cloud_wall" in ext) and (
                        ext.get("trazomob_wall", {}).get("motion_locked", False)
                        or ext.get("corte_cloud_wall", {}).get("motion_locked", False)
                    ):
                        return True
                return orig_is_locked(group)

            move_mod._is_locked = hooked_is_locked

        # Hook em MoveTool._commit para sincronizar automaticamente a posição da luz com o render e a sidebar
        MoveTool = getattr(move_mod, "MoveTool", None)
        if MoveTool is not None:
            orig_commit = MoveTool._commit

            def hooked_commit(self, viewport, delta):
                orig_commit(self, viewport, delta)
                try:
                    from .light_tools import sync_scene_lights_to_document
                    sync_scene_lights_to_document(viewport)
                except Exception as exc:
                    logger.debug("sincronização das luzes falhou após mover: %s", exc)

            MoveTool._commit = hooked_commit
    except Exception as e:
        logger.debug("Não foi possível plugar hook em tools.move: %s", e)


def _patch_scale_tool() -> None:
    try:
        import tools.scale as scale_mod
        from PySide6.QtGui import QVector3D
        ScaleTool = getattr(scale_mod, "ScaleTool", None)
        if ScaleTool is None:
            return

        orig_snap_point = ScaleTool._snap_point

        def hooked_snap_point(self, viewport, sx, sy):
            got = orig_snap_point(self, viewport, sx, sy)
            if got is not None:
                return got

            # Intercepta réguas de parede durante a escala
            groups = getattr(self, "_groups", [])
            # Esquadrias (portas e janelas) não sofrem snap de régua de marcenaria
            def _is_esquadria(grp):
                if grp and hasattr(grp, "ext") and isinstance(grp.ext, dict) and "trazomob_esquadria" in grp.ext:
                    return True
                if getattr(grp, "layer", "") == "ESQUADRIAS":
                    return True
                return False

            if not any(_is_trazomob_module(g) for g in groups) or any(_is_esquadria(g) for g in groups):
                return None
            grip = getattr(self, "_grip", None)
            anchor = getattr(self, "_anchor", None)
            if grip is not None and 2 in grip.mask and anchor is not None:
                try:
                    from .wall_guides import WallGuideRulerManager
                    ruler_mgr = WallGuideRulerManager.get_instance()
                    if ruler_mgr.visible and ruler_mgr.snap_enabled:
                        factors_est = self._factors_from_cursor(viewport, sx, sy)
                        if factors_est is not None:
                            g0 = self._grip_pos(grip)
                            est_z = anchor.z() + (g0.z() - anchor.z()) * factors_est[2]
                            snap_res = ruler_mgr.snap_to_levels(est_z, threshold_m=0.08)
                            if snap_res is not None:
                                snapped_z = snap_res[0]
                                snapped_pt = QVector3D(g0.x(), g0.y(), snapped_z)
                                got_snapped = self._factors_from_point(snapped_pt)
                                if got_snapped is not None:
                                    return got_snapped
                except Exception as exc:
                    logger.debug("snap de nível no Scale falhou: %s", exc)
            return None

        ScaleTool._snap_point = hooked_snap_point

        # Intercepta captura inicial de vértices para manter módulos paramétricos
        orig_capture = ScaleTool._capture_originals

        def hooked_capture_originals(self, viewport):
            from PySide6.QtGui import QMatrix4x4
            orig_v = []
            orig_x = []
            has_mod = False
            for group in getattr(self, "_groups", []):
                if _is_trazomob_module(group):
                    has_mod = True
                    targets = getattr(group, "children", []) or [group]
                    for t in targets:
                        tmesh = getattr(t, "mesh", None)
                        if tmesh is not None and hasattr(tmesh, "vertices"):
                            orig_v.extend((tmesh, v, QVector3D(v.position)) for v in tmesh.vertices)
                elif getattr(group, "xform", None) is not None:
                    orig_x.append((group, QMatrix4x4(group.xform)))
                else:
                    targets = getattr(group, "children", []) or [group]
                    for t in targets:
                        tmesh = getattr(t, "mesh", None)
                        if tmesh is not None and hasattr(tmesh, "vertices"):
                            orig_v.extend((tmesh, v, QVector3D(v.position)) for v in tmesh.vertices)

            if has_mod:
                # scene.mesh (e nao loose_mesh) de proposito: _verts pertencem a malha em edicao
                mesh = viewport.scene.mesh
                orig_v.extend((mesh, v, QVector3D(v.position)) for v in getattr(self, "_verts", []))
                self._orig_v = orig_v
                self._orig_x = orig_x
                self._orig_im = [
                    (im, QVector3D(im.origin), QVector3D(im.u), QVector3D(im.v))
                    for im in getattr(self, "_images", [])
                ]
            else:
                orig_capture(self, viewport)

        ScaleTool._capture_originals = hooked_capture_originals

    except Exception as e:
        logger.debug("Não foi possível plugar hook em tools.scale: %s", e)


def _patch_history_commands() -> None:
    try:
        import copy
        from PySide6.QtGui import QVector3D
        from core.history import (
            RotateGroupCommand,
            ScaleGroupCommand,
            TranslateGroupCommand,
            invert_scale_factor,
        )
        from .builder import CabinetBuilder

        # 1. RotateGroupCommand
        orig_rot_do = RotateGroupCommand.do
        orig_rot_undo = RotateGroupCommand.undo

        def hooked_rot_do(self, scene):
            if _is_trazomob_module(self.group):
                CabinetBuilder.rotate_module(
                    self.group, self.degrees, center=self.center, axis=self.axis, scene=scene, update_param=True
                )
                return
            orig_rot_do(self, scene)

        def hooked_rot_undo(self, scene):
            if _is_trazomob_module(self.group):
                CabinetBuilder.rotate_module(
                    self.group, -self.degrees, center=self.center, axis=self.axis, scene=scene, update_param=True
                )
                return
            orig_rot_undo(self, scene)

        RotateGroupCommand.do = hooked_rot_do
        RotateGroupCommand.undo = hooked_rot_undo

        # 2. ScaleGroupCommand
        orig_scale_do = ScaleGroupCommand.do
        orig_scale_undo = ScaleGroupCommand.undo

        def hooked_scale_do(self, scene):
            if _is_trazomob_module(self.group):
                mod_key = _get_module_key(self.group)
                if getattr(self, "_mod_params_before", None) is None:
                    self._mod_params_before = copy.deepcopy(self.group.ext[mod_key])
                CabinetBuilder.scale_module(
                    self.group, self.center, self.factor, axes=self.axes, scene=scene, update_param=True
                )
                return
            orig_scale_do(self, scene)

        def hooked_scale_undo(self, scene):
            if _is_trazomob_module(self.group):
                CabinetBuilder.scale_module(
                    self.group, self.center, invert_scale_factor(self.factor),
                    axes=self.axes, scene=scene, update_param=False
                )
                if getattr(self, "_mod_params_before", None) is not None:
                    mod_key = _get_module_key(self.group)
                    self.group.ext[mod_key] = copy.deepcopy(self._mod_params_before)
                return
            orig_scale_undo(self, scene)

        ScaleGroupCommand.do = hooked_scale_do
        ScaleGroupCommand.undo = hooked_scale_undo

        # 3. TranslateGroupCommand
        orig_trans_shift = TranslateGroupCommand._shift

        def hooked_trans_shift(self, scene, delta):
            if _is_trazomob_module(self.group):
                targets = getattr(self.group, "children", []) or [self.group]
                for t_grp in targets:
                    m_sub = getattr(t_grp, "mesh", None)
                    if m_sub and hasattr(m_sub, "vertices"):
                        for v in m_sub.vertices:
                            v.position += delta
                        m_sub._mut_serial = getattr(m_sub, "_mut_serial", 0) + 1
                    if getattr(t_grp, "ext", None) is not None:
                        if "orig_vertices" in t_grp.ext and isinstance(t_grp.ext["orig_vertices"], list):
                            t_grp.ext["orig_vertices"] = [
                                orig + delta for orig in t_grp.ext["orig_vertices"] if isinstance(orig, QVector3D)
                            ]
                        if "hinge_pivot" in t_grp.ext and isinstance(t_grp.ext["hinge_pivot"], QVector3D):
                            t_grp.ext["hinge_pivot"] += delta
                mod_key = _get_module_key(self.group)
                mod_p = self.group.ext[mod_key]
                old_off = mod_p.get("offset", (0.0, 0.0, 0.0))
                if isinstance(old_off, (list, tuple)) and len(old_off) >= 3:
                    mod_p["offset"] = (
                        float(old_off[0]) + float(delta.x()),
                        float(old_off[1]) + float(delta.y()),
                        float(old_off[2]) + float(delta.z()),
                    )
                scene.version += 1
                return
            orig_trans_shift(self, scene, delta)

        TranslateGroupCommand._shift = hooked_trans_shift

    except Exception as e:
        logger.debug("Não foi possível plugar hook em core.history: %s", e)
