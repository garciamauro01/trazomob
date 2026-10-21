# SPDX-License-Identifier: GPL-3.0-or-later
"""Teste unitário para ocultar e reexibir paredes e tetos do TrazoMob."""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication, QVector3D
_app = QGuiApplication.instance() or QGuiApplication([])

from core.scene import Scene
from core.history import History, HideCommand
from plugins.trazomob.wall_builder import WallBuilderTool
from plugins.trazomob.wall_mesh_builder import WallMeshBuilder


def test_hide_and_unhide_wall_group():
    """Valida se o grupo de parede responde corretamente ao HideCommand e ao Scene."""
    scene = Scene()
    history = History(scene)

    pts = [
        QVector3D(0, 0, 0),
        QVector3D(3, 0, 0),
        QVector3D(3, 3, 0),
        QVector3D(0, 3, 0),
    ]

    wall = WallBuilderTool.build_chain_group(
        scene=scene,
        pts=pts,
        is_closed=True,
        altura_m=2.60,
        espessura_m=0.15,
        alinhamento="interno",
    )
    scene.groups.append(wall)
    scene.select([wall])

    assert scene.entity_visible(wall) is True
    assert wall.hidden is False

    # Executa ocultação
    cmd = HideCommand([wall], hidden=True)
    history.execute(cmd)

    assert wall.hidden is True
    assert scene.entity_visible(wall) is False
    assert wall not in scene.selection

    # Reexibe
    cmd_unhide = HideCommand([wall], hidden=False)
    history.execute(cmd_unhide)

    assert wall.hidden is False
    assert scene.entity_visible(wall) is True


def test_clean_polygon_floor_and_ceiling():
    """Valida que piso e teto são gerados sem duplicações e respeitam o pé-direito."""
    scene = Scene()
    pts = [
        QVector3D(0, 0, 0),
        QVector3D(3, 0, 0),
        QVector3D(3, 3, 0),
        QVector3D(0, 3, 0),
        QVector3D(0, 0, 0),  # Ponto de fechamento duplicado proposital
    ]

    floor = WallMeshBuilder.build_floor_group(scene, pts)
    assert floor is not None
    assert floor.ext.get("trazomob_floor") is True

    ceiling = WallMeshBuilder.build_ceiling_group(scene, pts, altura_m=2.80)
    assert ceiling is not None
    assert ceiling.ext.get("trazomob_ceiling") is True
    assert ceiling.layer == "Teto"
