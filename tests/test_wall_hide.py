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


def test_hide_individual_wall_segment():
    """Valida se ocultar um segmento de parede oculta somente suas faces, mantendo as demais visíveis."""
    scene = Scene()
    history = History(scene)

    pts = [
        QVector3D(0, 0, 0),
        QVector3D(4, 0, 0),
        QVector3D(4, 3, 0),
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

    params = wall.ext.get("trazomob_wall", {})
    face_map = params.get("face_segment_map", {})
    assert len(face_map) > 0

    # Localiza faces do segmento #0 (Parede 1)
    seg0_faces = [wall.mesh.faces[f_idx] for f_idx, s in face_map.items() if s == 0]
    seg1_faces = [wall.mesh.faces[f_idx] for f_idx, s in face_map.items() if s == 1]
    # Cada parede/segmento tem 6 faces fechadas (base, topo, face ext, face int e cortes nas quinas)
    assert len(seg0_faces) == 6
    assert len(seg1_faces) == 6

    # Oculta apenas as faces do segmento #0
    cmd = HideCommand(seg0_faces, hidden=True)
    history.execute(cmd)

    # Verifica que o grupo como um todo NÃO foi ocultado, mas as faces do segmento 0 sim
    assert wall.hidden is False
    for f in seg0_faces:
        assert f.attrs.get("hidden") is True
        assert scene.entity_visible(f) is False

    # Outras paredes permanecem visíveis
    for f in seg1_faces:
        assert f.attrs.get("hidden") is not True
        assert scene.entity_visible(f) is True

    # Reexibe o segmento #0
    cmd_unhide = HideCommand(seg0_faces, hidden=False)
    history.execute(cmd_unhide)
    for f in seg0_faces:
        assert f.attrs.get("hidden") is not True
        assert scene.entity_visible(f) is True


def test_wall_builder_creates_ceiling_when_configured():
    """Valida que o WallBuilderTool gera parede, piso e teto na altura configurada ao fechar o perímetro."""
    scene = Scene()
    history = History(scene)

    class DummyViewport:
        def __init__(self, sc, hist):
            self.scene = sc
            self.history = hist
            self.updated = False
            self.status_msg = ""
        def update(self):
            self.updated = True
        def flash_status(self, msg):
            self.status_msg = msg

    class DummyContext:
        def __init__(self, vp, world_pt):
            self.viewport = vp
            self.world = world_pt

    vp = DummyViewport(scene, history)
    tool = WallBuilderTool(altura_m=2.70, espessura_m=0.15, gerar_teto=True)

    # Simula 4 cliques formando um retângulo e fechando no ponto 0
    coords = [
        QVector3D(0, 0, 0),
        QVector3D(5, 0, 0),
        QVector3D(5, 4, 0),
        QVector3D(0, 4, 0),
        QVector3D(0, 0, 0),  # Fechamento
    ]
    for pt in coords:
        ctx = DummyContext(vp, pt)
        tool.on_click(ctx)

    # Verifica se foram gerados 3 grupos no total: Parede, Piso e Teto
    groups = scene.groups
    assert len(groups) == 3

    wall_grp = next((g for g in groups if "trazomob_wall" in getattr(g, "ext", {})), None)
    floor_grp = next((g for g in groups if getattr(g, "ext", {}).get("trazomob_floor")), None)
    ceiling_grp = next((g for g in groups if getattr(g, "ext", {}).get("trazomob_ceiling")), None)

    assert wall_grp is not None
    assert floor_grp is not None
    assert ceiling_grp is not None
    assert ceiling_grp.layer == "Teto"

    # Confirma que a face inferior do teto está na altura de 2.70m
    z_coords = [v.position.z() for v in ceiling_grp.mesh.vertices]
    assert any(abs(z - 2.70) < 1e-4 for z in z_coords)

