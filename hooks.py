# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors and Pair Programmer.
"""Ganchos de runtime que o TrazoMob precisa e o host ainda não expõe.

Este módulo NÃO instala nada por conta própria: cada interceptação passa por
``platform.install_hook``, que a registra, instala uma única vez e permite
desfazê-la. Assim:

* instalar duas vezes é inofensivo (``setup`` pode ser chamado de novo);
* um host sem o atributo gera um ``INFO`` no log, não um traceback;
* quando o IngeTrazo ganhar o gancho oficial, a entrada correspondente sai
  daqui sem tocar no resto do plugin.

Os ganchos cobrem hoje cinco buracos da API de extensões:

1. ``render.blend``      — tipo de luz ``led_strip`` e campos p1/p2/target;
2. ``group.copy``        — malhas independentes ao copiar módulo;
3. ``move.lock``         — ``motion_locked`` respeitado pelo Move;
4. ``move.commit``       — luzes sincronizadas após mover;
5. ``scale.*``           — réguas e regeneração paramétrica ao escalar;
6. ``history.*``         — undo/redo paramétrico de girar, escalar, mover.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

from . import platform as host

logger = logging.getLogger("trazomob.hooks")


# ---------------------------------------------------------------------------
# Identificação de módulos do TrazoMob
# ---------------------------------------------------------------------------

MODULE_KEYS = ("trazomob_module", "corte_cloud_module", "hellomob_module")


def _is_trazomob_module(group: Any) -> bool:
    if group is None:
        return False
    ext = getattr(group, "ext", None)
    if not isinstance(ext, dict):
        return False
    return any(key in ext for key in MODULE_KEYS)


def _get_module_key(group: Any) -> str:
    ext = getattr(group, "ext", {}) or {}
    for key in MODULE_KEYS:
        if key in ext:
            return key
    return MODULE_KEYS[-1]


def _module_params(group: Any) -> dict:
    return group.ext.get(_get_module_key(group), {})


# ---------------------------------------------------------------------------
# Entrada única
# ---------------------------------------------------------------------------

def apply_runtime_hooks() -> None:
    """Instala os ganchos (uma vez) sem alterar os arquivos do IngeTrazo."""
    _patch_render_blender_lights()
    _patch_group_copy()
    _patch_move_tool()
    _patch_scale_tool()
    _patch_history_commands()
    if host.installed_hooks():
        logger.debug("ganchos ativos: %s", ", ".join(host.installed_hooks()))


# ---------------------------------------------------------------------------
# 1. core.render_blender
# ---------------------------------------------------------------------------

def _patch_render_blender_lights() -> None:
    rb = host.import_module("core.render_blender")
    if rb is None:
        return
    try:
        if "led_strip" not in rb.LIGHT_KINDS:
            rb.LIGHT_KINDS = (*rb.LIGHT_KINDS, "led_strip")
        if "led_strip" not in rb.DEFAULT_POWER:
            rb.DEFAULT_POWER["led_strip"] = 350.0
    except Exception:
        logger.exception("não foi possível estender os tipos de luz do host")

    extra_fields = ("target", "p1", "p2", "length", "profile_w")

    def make_clean_lights(original):
        def hooked_clean_lights(raw):
            cleaned = original(raw)
            raw_list = raw if isinstance(raw, list) else []
            for i, light in enumerate(cleaned):
                if i >= len(raw_list) or not isinstance(raw_list[i], dict):
                    continue
                source = raw_list[i]
                for field in extra_fields:
                    if field in source and field not in light:
                        light[field] = source[field]
                if source.get("kind") == "led_strip":
                    light["kind"] = "led_strip"
            return cleaned
        return hooked_clean_lights

    host.install_hook("render.led_lights", rb, "clean_lights", make_clean_lights)


# ---------------------------------------------------------------------------
# 2. core.group.copy_group
# ---------------------------------------------------------------------------

def _unshare_trazomob_module_meshes(group: Any) -> None:
    """Dá malha própria a cada peça filha de um módulo copiado, para que
    girar/editar a cópia não afete o original."""
    from core.group import transformed_mesh
    from PySide6.QtGui import QMatrix4x4

    identity = QMatrix4x4()

    def _walk(node):
        for child in getattr(node, "children", []) or []:
            if getattr(child, "mesh", None) is not None:
                child.mesh = transformed_mesh(child.mesh, identity)
            _walk(child)

    _walk(group)


def _patch_group_copy() -> None:
    grp_mod = host.import_module("core.group")
    if grp_mod is None:
        return

    def make_copy_group(original):
        def hooked_copy_group(group, delta=None, _in_definition=False):
            new_group = original(group, delta=delta, _in_definition=_in_definition)
            if _is_trazomob_module(new_group):
                _unshare_trazomob_module_meshes(new_group)
            return new_group
        return hooked_copy_group

    if not host.install_hook("group.copy", grp_mod, "copy_group", make_copy_group):
        return

    # Módulos de ferramentas que importaram copy_group por nome precisam da
    # mesma função, senão a cópia feita por eles continua compartilhando malha.
    patched = getattr(grp_mod, "copy_group")
    for module_name in ("tools.move", "tools.rotate", "tools.paste", "tools.flip"):
        module = sys.modules.get(module_name)
        if module is not None:
            try:
                setattr(module, "copy_group", patched)
            except Exception:
                logger.debug("copy_group não atualizado em %s", module_name)


# ---------------------------------------------------------------------------
# 3 e 4. tools.move
# ---------------------------------------------------------------------------

def _motion_locked(group: Any) -> bool:
    """``motion_locked`` é um conceito do TrazoMob (paredes/piso do projeto),
    guardado no ``ext`` do grupo."""
    if group is None:
        return False
    if getattr(group, "motion_locked", False):
        return True
    ext = getattr(group, "ext", None)
    if not isinstance(ext, dict):
        return False
    if ext.get("motion_locked"):
        return True
    wall = ext.get("trazomob_wall") or ext.get("corte_cloud_wall")
    return isinstance(wall, dict) and bool(wall.get("motion_locked", False))


def _patch_move_tool() -> None:
    move_mod = host.import_module("tools.move")
    if move_mod is None:
        return

    def make_gather_targets(original):
        def hooked_gather_targets(ctx):
            groups, positions = original(ctx)
            if any(_motion_locked(g) for g in groups):
                groups = [g for g in groups if not _motion_locked(g)]
            return groups, positions
        return hooked_gather_targets

    if host.install_hook("move.lock", move_mod, "gather_targets",
                         make_gather_targets):
        # Rotate e Scale importaram gather_targets por nome.
        patched = move_mod.gather_targets
        for module_name in ("tools.rotate", "tools.scale"):
            module = sys.modules.get(module_name)
            if module is not None:
                setattr(module, "gather_targets", patched)

    move_tool = getattr(move_mod, "MoveTool", None)
    if move_tool is not None:
        def make_commit(original):
            def hooked_commit(self, viewport, delta):
                original(self, viewport, delta)
                try:
                    from .light_tools import sync_scene_lights_to_document
                    sync_scene_lights_to_document(viewport)
                except Exception as exc:
                    logger.debug("sincronização das luzes falhou após mover: %s", exc)
            return hooked_commit

        host.install_hook("move.commit", move_tool, "_commit", make_commit)


# ---------------------------------------------------------------------------
# 5. tools.scale
# ---------------------------------------------------------------------------

def _patch_scale_tool() -> None:
    scale_mod = host.import_module("tools.scale")
    if scale_mod is None:
        return
    scale_tool = getattr(scale_mod, "ScaleTool", None)
    if scale_tool is None:
        return

    def make_factors_for(original):
        def hooked_factors_for(self, ctx, viewport, sx, sy):
            got = original(self, ctx, viewport, sx, sy)

            # Um ponto nomeado (endpoint, midpoint...) vence: o usuário mirou nele.
            try:
                if self._snapped_point(ctx) is not None:
                    return got
            except Exception:
                pass

            groups = getattr(self, "_groups", [])

            def _is_esquadria(group):
                ext = getattr(group, "ext", None)
                if isinstance(ext, dict) and "trazomob_esquadria" in ext:
                    return True
                return getattr(group, "layer", "") == "ESQUADRIAS"

            if not any(_is_trazomob_module(g) for g in groups):
                return got
            if any(_is_esquadria(g) for g in groups):
                return got

            grip = getattr(self, "_grip", None)
            anchor = getattr(self, "_anchor", None)
            if grip is None or 2 not in grip.mask or anchor is None:
                return got
            try:
                from .wall_guides import WallGuideRulerManager
                from PySide6.QtGui import QVector3D

                ruler_mgr = WallGuideRulerManager.get_instance()
                if not (ruler_mgr.visible and ruler_mgr.snap_enabled):
                    return got
                factors_est = self._factors_from_cursor(viewport, sx, sy)
                if factors_est is None:
                    return got
                grip_pos = self._grip_pos(grip)
                est_z = anchor.z() + (grip_pos.z() - anchor.z()) * factors_est[2]
                snap_res = ruler_mgr.snap_to_levels(est_z, threshold_m=0.08)
                if snap_res is None:
                    return got
                snapped = QVector3D(grip_pos.x(), grip_pos.y(), snap_res[0])
                return self._factors_from_point(snapped) or got
            except Exception as exc:
                logger.debug("snap de nível no Scale falhou: %s", exc)
                return got
        return hooked_factors_for

    host.install_hook("scale.ruler_snap", scale_tool, "_factors_for", make_factors_for)

    def make_capture_originals(original):
        def hooked_capture_originals(self, viewport):
            from PySide6.QtGui import QMatrix4x4, QVector3D

            orig_vertices = []
            orig_xforms = []
            has_module = False
            for group in getattr(self, "_groups", []):
                if _is_trazomob_module(group):
                    has_module = True
                    targets = getattr(group, "children", []) or [group]
                    for target in targets:
                        mesh = getattr(target, "mesh", None)
                        if mesh is not None and hasattr(mesh, "vertices"):
                            orig_vertices.extend(
                                (mesh, v, QVector3D(v.position)) for v in mesh.vertices)
                elif getattr(group, "xform", None) is not None:
                    orig_xforms.append((group, QMatrix4x4(group.xform)))
                else:
                    targets = getattr(group, "children", []) or [group]
                    for target in targets:
                        mesh = getattr(target, "mesh", None)
                        if mesh is not None and hasattr(mesh, "vertices"):
                            orig_vertices.extend(
                                (mesh, v, QVector3D(v.position)) for v in mesh.vertices)

            if not has_module:
                original(self, viewport)
                return

            # scene.mesh (não loose_mesh) de propósito: _verts pertencem à
            # malha em edição.
            mesh = viewport.scene.mesh
            orig_vertices.extend(
                (mesh, v, QVector3D(v.position)) for v in getattr(self, "_verts", []))
            self._orig_v = orig_vertices
            self._orig_x = orig_xforms
            self._orig_im = [
                (im, QVector3D(im.origin), QVector3D(im.u), QVector3D(im.v))
                for im in getattr(self, "_images", [])
            ]
        return hooked_capture_originals

    host.install_hook("scale.capture", scale_tool, "_capture_originals",
                      make_capture_originals)


# ---------------------------------------------------------------------------
# 6. core.history
# ---------------------------------------------------------------------------

def _patch_history_commands() -> None:
    history = host.import_module("core.history")
    if history is None:
        return
    from .builder import CabinetBuilder

    def make_rotate(degrees_sign):
        def factory(original):
            def hooked(self, scene):
                if _is_trazomob_module(self.group):
                    CabinetBuilder.rotate_module(
                        self.group, degrees_sign * self.degrees,
                        center=self.center, axis=self.axis, scene=scene,
                        update_param=True)
                    return
                original(self, scene)
            return hooked
        return factory

    if hasattr(history, "RotateGroupCommand"):
        host.install_hook("history.rotate.do", history.RotateGroupCommand, "do",
                          make_rotate(1))
        host.install_hook("history.rotate.undo", history.RotateGroupCommand, "undo",
                          make_rotate(-1))

    def make_scale(forward):
        def factory(original):
            def hooked(self, scene):
                if _is_trazomob_module(self.group):
                    if forward:
                        if getattr(self, "_mod_params_before", None) is None:
                            import copy
                            self._mod_params_before = copy.deepcopy(
                                _module_params(self.group))
                        CabinetBuilder.scale_module(
                            self.group, self.center, self.factor, axes=self.axes,
                            scene=scene, update_param=True)
                    else:
                        import copy
                        CabinetBuilder.scale_module(
                            self.group, self.center,
                            history.invert_scale_factor(self.factor),
                            axes=self.axes, scene=scene, update_param=False)
                        if getattr(self, "_mod_params_before", None) is not None:
                            self.group.ext[_get_module_key(self.group)] = copy.deepcopy(
                                self._mod_params_before)
                    return
                original(self, scene)
            return hooked
        return factory

    if hasattr(history, "ScaleGroupCommand"):
        host.install_hook("history.scale.do", history.ScaleGroupCommand, "do",
                          make_scale(True))
        host.install_hook("history.scale.undo", history.ScaleGroupCommand, "undo",
                          make_scale(False))

    def make_translate(original):
        def hooked(self, scene, delta):
            if not _is_trazomob_module(self.group):
                original(self, scene, delta)
                return

            from PySide6.QtGui import QVector3D

            for target in getattr(self.group, "children", []) or [self.group]:
                mesh = getattr(target, "mesh", None)
                if mesh is not None and hasattr(mesh, "vertices"):
                    for vertex in mesh.vertices:
                        vertex.position += delta
                    mesh._mut_serial = getattr(mesh, "_mut_serial", 0) + 1
                ext = getattr(target, "ext", None)
                if isinstance(ext, dict):
                    if isinstance(ext.get("orig_vertices"), list):
                        ext["orig_vertices"] = [
                            origin + delta for origin in ext["orig_vertices"]
                            if isinstance(origin, QVector3D)
                        ]
                    hinge = ext.get("hinge_pivot")
                    if isinstance(hinge, QVector3D):
                        ext["hinge_pivot"] = hinge + delta

            params = _module_params(self.group)
            offset = params.get("offset", (0.0, 0.0, 0.0))
            if isinstance(offset, (list, tuple)) and len(offset) >= 3:
                params["offset"] = (
                    float(offset[0]) + float(delta.x()),
                    float(offset[1]) + float(delta.y()),
                    float(offset[2]) + float(delta.z()),
                )
            scene.version += 1
        return hooked

    if hasattr(history, "MoveGroupCommand"):
        host.install_hook("history.move", history.MoveGroupCommand,
                          "_shift", make_translate)
