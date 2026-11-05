# SPDX-License-Identifier: GPL-3.0-or-later
"""Ferramentas de Alinhamento e Centralização de Objetos no Espaço 3D (TrazoMob).

Permite centralizar um objeto móvel em relação a um objeto base (ou vice-versa),
ou alinhar faces/bordas nos eixos X (largura), Y (profundidade) e Z (altura).
Suporta Groups de marcenaria, peças soltas, e entidades em geral com histórico Undo/Redo.
"""
from __future__ import annotations

from typing import Optional, Tuple, List
from PySide6.QtGui import QVector3D
from core.group import Group, iter_placements
from core.history import MoveGroupCommand, CompoundCommand


def get_entity_world_bounds(entity) -> Optional[Tuple[float, float, float, float, float, float]]:
    """Retorna os limites AABB (min_x, max_x, min_y, max_y, min_z, max_z) em metros no espaço global."""
    if entity is None:
        return None

    # Se for um Group ou módulo
    if isinstance(entity, Group):
        min_x, max_x = float("inf"), float("-inf")
        min_y, max_y = float("inf"), float("-inf")
        min_z, max_z = float("inf"), float("-inf")
        found = False

        for pg, xf in iter_placements(entity):
            mesh = getattr(pg, "mesh", None)
            if mesh is not None and getattr(mesh, "vertices", None):
                for v in mesh.vertices:
                    p = getattr(v, "position", v)
                    if xf is not None:
                        p = xf.map(p)
                    min_x = min(min_x, p.x())
                    max_x = max(max_x, p.x())
                    min_y = min(min_y, p.y())
                    max_y = max(max_y, p.y())
                    min_z = min(min_z, p.z())
                    max_z = max(max_z, p.z())
                    found = True

        if found:
            return (min_x, max_x, min_y, max_y, min_z, max_z)

    # Se for uma Face ou Edge solta
    pts = []
    if hasattr(entity, "vertices"):
        pts = [getattr(v, "position", v) for v in entity.vertices]
    elif hasattr(entity, "a") and hasattr(entity, "b"):
        pts = [entity.a, entity.b]

    if pts:
        xs = [p.x() for p in pts]
        ys = [p.y() for p in pts]
        zs = [p.z() for p in pts]
        return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

    return None


def center_objects(
    target_group: Group,
    reference_entity,
    axes: str = "xy",
    viewport=None
) -> Optional[QVector3D]:
    """Centraliza `target_group` em relação a `reference_entity`.
    
    :param target_group: Objeto / Grupo que será movido.
    :param reference_entity: Objeto / Grupo / Parede de referência que ficará parado.
    :param axes: 'x' (apenas largura), 'y' (apenas profundidade), 'z' (apenas altura),
                 'xy' (plano horizontal), ou 'xyz' (centro tridimensional completo).
    :param viewport: Instância do viewport do IngeTrazo para executar o comando com Undo/Redo.
    :return: Vetor delta aplicado, ou None em caso de falha.
    """
    if target_group is None or reference_entity is None:
        return None
    if target_group is reference_entity:
        return None

    b_target = get_entity_world_bounds(target_group)
    b_ref = get_entity_world_bounds(reference_entity)

    if not b_target or not b_ref:
        return None

    # Centros atuais
    c_target_x = (b_target[0] + b_target[1]) * 0.5
    c_target_y = (b_target[2] + b_target[3]) * 0.5
    c_target_z = (b_target[4] + b_target[5]) * 0.5

    c_ref_x = (b_ref[0] + b_ref[1]) * 0.5
    c_ref_y = (b_ref[2] + b_ref[3]) * 0.5
    c_ref_z = (b_ref[4] + b_ref[5]) * 0.5

    dx = (c_ref_x - c_target_x) if "x" in axes.lower() else 0.0
    dy = (c_ref_y - c_target_y) if "y" in axes.lower() else 0.0
    dz = (c_ref_z - c_target_z) if "z" in axes.lower() else 0.0

    delta = QVector3D(dx, dy, dz)
    if delta.length() < 1e-5:
        if viewport and hasattr(viewport, "flash_status"):
            viewport.flash_status("Objetos já estão centralizados!")
        return delta

    if viewport and hasattr(viewport, "history"):
        cmd = MoveGroupCommand(target_group, delta)
        viewport.history.execute(cmd)
        if hasattr(viewport, "notify_scene_changed"):
            viewport.notify_scene_changed()
        viewport.update()

        # Mensagem de feedback na barra de status
        axes_label = axes.upper()
        if hasattr(viewport, "flash_status"):
            name_t = getattr(target_group, "name", "Objeto")
            name_r = getattr(reference_entity, "name", "Referência")
            viewport.flash_status(f"🎯 Centralizado [{axes_label}]: {name_t} em relação a {name_r}")

    return delta
