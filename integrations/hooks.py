# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors and Pair Programmer.
"""Ganchos de runtime que o TrazoMob precisa do IngeTrazo.

Ordem de preferência, sempre:

1. **API oficial de extensões** (``app.add_group_transform_hook``,
   ``add_group_copy_hook``, ``add_move_filter``, ``register_light_kind``).
   É o caminho normal num IngeTrazo atual e não toca no código do host.
2. **Monkeypatch registrado** (``platform.install_hook``) apenas para o que
   a API ainda não expõe — hoje, o snap de réguas no Scale, a captura de
   vértices do Scale e a sincronização de luzes após mover. Instala uma
   única vez, loga quando o atributo do host sumiu e pode ser revertido.

Assim o plugin funciona em hosts novos (API) e antigos (patch), e a dívida
de monkeypatch fica visível em ``platform.installed_hooks()``.
"""
from __future__ import annotations

import copy
import logging
import sys
from typing import Any

from . import platform as host

logger = logging.getLogger("trazomob.hooks")

#: Chaves de metadados dos módulos.
MODULE_KEYS = ("trazomob_module",)

#: Campos próprios de uma fita de LED que o render deve preservar.
LED_EXTRA_FIELDS = ("target", "p1", "p2", "length", "profile_w")


# ---------------------------------------------------------------------------
# Identificação de módulos e de grupos travados
# ---------------------------------------------------------------------------

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


def _motion_locked(group: Any) -> bool:
    """``motion_locked``: paredes e piso do projeto não se movem."""
    if group is None:
        return False
    if getattr(group, "motion_locked", False):
        return True
    ext = getattr(group, "ext", None)
    if not isinstance(ext, dict):
        return False
    if ext.get("motion_locked"):
        return True
    wall = ext.get("trazomob_wall")
    return isinstance(wall, dict) and bool(wall.get("motion_locked", False))


# ---------------------------------------------------------------------------
# Entrada única
# ---------------------------------------------------------------------------

def apply_runtime_hooks(app=None) -> None:
    """Instala os ganchos; ``app`` é o ``ExtensionApp`` de ``setup``.

    Com ``app``, usa a API oficial e só recorre a monkeypatch no que ela não
    cobre. Sem ``app`` (teste, host antigo), instala tudo por patch.
    """
    official = _install_official(app)

    if not official.get("light_kind"):
        _patch_render_blender_lights()
    if not official.get("copy"):
        _patch_group_copy()
    if not official.get("move_filter"):
        _patch_move_lock()
    if not official.get("transform"):
        _patch_history_commands()

    # Pontos que a API de extensões ainda não expõe.
    _patch_move_commit()
    _patch_scale_tool()

    if host.installed_hooks():
        logger.debug("ganchos de patch ativos: %s",
                     ", ".join(host.installed_hooks()))


# ---------------------------------------------------------------------------
# API oficial de extensões
# ---------------------------------------------------------------------------

def _install_official(app) -> dict[str, bool]:
    """Registra na API oficial o que o host oferecer; devolve o que foi."""
    done: dict[str, bool] = {}
    if app is None:
        return done

    register_light = getattr(app, "register_light_kind", None)
    if callable(register_light):
        register_light("led_strip", 350.0, LED_EXTRA_FIELDS)
        done["light_kind"] = True

    add_copy_hook = getattr(app, "add_group_copy_hook", None)
    if callable(add_copy_hook):
        add_copy_hook(_on_group_copied)
        done["copy"] = True

    add_move_filter = getattr(app, "add_move_filter", None)
    if callable(add_move_filter):
        add_move_filter(_movable_groups)
        done["move_filter"] = True

    add_transform = getattr(app, "add_group_transform_hook", None)
    if callable(add_transform):
        add_transform(_official_transform)
        done["transform"] = True

    return done


def _on_group_copied(group: Any) -> None:
    if _is_trazomob_module(group):
        _unshare_trazomob_module_meshes(group)


def _movable_groups(groups: list) -> list:
    return [g for g in groups if not _motion_locked(g)]


def _official_transform(command: Any, scene: Any, phase: str) -> bool:
    """Move/gira/escala paramétricos pelo caminho oficial (do e undo)."""
    group = getattr(command, "group", None)
    if not _is_trazomob_module(group):
        return False

    from core.history import (MoveGroupCommand, RotateGroupCommand,
                              ScaleGroupCommand, invert_scale_factor)
    from ..builders.cabinet import CabinetBuilder

    forward = phase != "undo"

    if isinstance(command, RotateGroupCommand):
        CabinetBuilder.rotate_module(
            group, command.degrees if forward else -command.degrees,
            center=command.center, axis=command.axis, scene=scene,
            update_param=True)
        return True

    if isinstance(command, ScaleGroupCommand):
        if forward:
            if getattr(command, "_mod_params_before", None) is None:
                command._mod_params_before = copy.deepcopy(_module_params(group))
            CabinetBuilder.scale_module(
                group, command.center, command.factor, axes=command.axes,
                scene=scene, update_param=True)
        else:
            CabinetBuilder.scale_module(
                group, command.center, invert_scale_factor(command.factor),
                axes=command.axes, scene=scene, update_param=False)
            if getattr(command, "_mod_params_before", None) is not None:
                group.ext[_get_module_key(group)] = copy.deepcopy(
                    command._mod_params_before)
        return True

    if isinstance(command, MoveGroupCommand):
        _translate_module(group, scene,
                          command.delta if forward else -command.delta)
        return True

    return False


def _translate_module(group: Any, scene: Any, delta) -> None:
    """Move as peças do módulo e o offset paramétrico (usado do e undo)."""
    from PySide6.QtGui import QVector3D

    for target in getattr(group, "children", []) or [group]:
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

    params = _module_params(group)
    offset = params.get("offset", (0.0, 0.0, 0.0))
    if isinstance(offset, (list, tuple)) and len(offset) >= 3:
        params["offset"] = (
            float(offset[0]) + float(delta.x()),
            float(offset[1]) + float(delta.y()),
            float(offset[2]) + float(delta.z()),
        )
    scene.version += 1


# ---------------------------------------------------------------------------
# Reserva: core.render_blender (host sem register_light_kind)
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

    def make_clean_lights(original):
        def hooked_clean_lights(raw):
            cleaned = original(raw)
            raw_list = raw if isinstance(raw, list) else []
            for i, light in enumerate(cleaned):
                if i >= len(raw_list) or not isinstance(raw_list[i], dict):
                    continue
                source = raw_list[i]
                for field in LED_EXTRA_FIELDS:
                    if field in source and field not in light:
                        light[field] = source[field]
                if source.get("kind") == "led_strip":
                    light["kind"] = "led_strip"
            return cleaned
        return hooked_clean_lights

    host.install_hook("render.led_lights", rb, "clean_lights", make_clean_lights)


# ---------------------------------------------------------------------------
# Reserva: core.group.copy_group
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
            _on_group_copied(new_group)
            return new_group
        return hooked_copy_group

    if not host.install_hook("group.copy", grp_mod, "copy_group", make_copy_group):
        return

    patched = getattr(grp_mod, "copy_group")
    for module_name in ("tools.move", "tools.rotate", "tools.paste", "tools.flip"):
        module = sys.modules.get(module_name)
        if module is not None:
            try:
                setattr(module, "copy_group", patched)
            except Exception:
                logger.debug("copy_group não atualizado em %s", module_name)


# ---------------------------------------------------------------------------
# Reserva: tools.move (trava) e pós-movimento (sempre por patch)
# ---------------------------------------------------------------------------

def _patch_move_lock() -> None:
    move_mod = host.import_module("tools.move")
    if move_mod is None:
        return

    def make_gather_targets(original):
        def hooked_gather_targets(ctx):
            groups, positions = original(ctx)
            return _movable_groups(groups), positions
        return hooked_gather_targets

    if host.install_hook("move.lock", move_mod, "gather_targets",
                         make_gather_targets):
        patched = move_mod.gather_targets
        for module_name in ("tools.rotate", "tools.scale"):
            module = sys.modules.get(module_name)
            if module is not None:
                setattr(module, "gather_targets", patched)


def _patch_move_commit() -> None:
    move_mod = host.import_module("tools.move")
    if move_mod is None:
        return
    from PySide6.QtGui import QVector3D

    def hook_post_move(original):
        def hooked_commit(self, viewport, delta: QVector3D):
            original(self, viewport, delta)
            try:
                from ..render.lighting import sync_scene_lights_to_document
                sync_scene_lights_to_document(viewport)
            except Exception as exc:
                logger.debug("sincronização das luzes falhou após mover: %s", exc)
        return hooked_commit

    move_tool = getattr(move_mod, "MoveTool", None)
    if move_tool is not None:
        host.install_hook("move.commit", move_tool, "_commit", hook_post_move)


# ---------------------------------------------------------------------------
# Reserva: tools.scale (snap de réguas e captura paramétrica)
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
                from ..wall.guides import WallGuideRulerManager
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
# Reserva: core.history (host sem add_group_transform_hook)
# ---------------------------------------------------------------------------

def _patch_history_commands() -> None:
    history = host.import_module("core.history")
    if history is None:
        return

    from ..builders.cabinet import CabinetBuilder

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
                if not _is_trazomob_module(self.group):
                    original(self, scene)
                    return
                if forward:
                    if getattr(self, "_mod_params_before", None) is None:
                        self._mod_params_before = copy.deepcopy(
                            _module_params(self.group))
                    CabinetBuilder.scale_module(
                        self.group, self.center, self.factor, axes=self.axes,
                        scene=scene, update_param=True)
                else:
                    CabinetBuilder.scale_module(
                        self.group, self.center,
                        history.invert_scale_factor(self.factor),
                        axes=self.axes, scene=scene, update_param=False)
                    if getattr(self, "_mod_params_before", None) is not None:
                        self.group.ext[_get_module_key(self.group)] = copy.deepcopy(
                            self._mod_params_before)
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
            _translate_module(self.group, scene, delta)
        return hooked

    if hasattr(history, "MoveGroupCommand"):
        host.install_hook("history.move", history.MoveGroupCommand,
                          "_shift", make_translate)
