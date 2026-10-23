# SPDX-License-Identifier: GPL-3.0-or-later
"""Testes para cinemática contínua de abertura e detecção de colisões visuais."""
import pytest
from PySide6.QtGui import QVector3D
from core.scene import Scene
from core.group import Group
from core.mesh import Mesh
from plugins.trazomob.interact import CabinetInteract
from plugins.trazomob.collision import check_opening_collisions, aabb_intersect, get_piece_aabb


def _create_box_mesh(min_x, max_x, min_y, max_y, min_z, max_z):
    mesh = Mesh()
    pts = [
        QVector3D(min_x, min_y, min_z),
        QVector3D(max_x, min_y, min_z),
        QVector3D(max_x, max_y, min_z),
        QVector3D(min_x, max_y, min_z),
        QVector3D(min_x, min_y, max_z),
        QVector3D(max_x, min_y, max_z),
        QVector3D(max_x, max_y, max_z),
        QVector3D(min_x, max_y, max_z),
    ]
    # Cria faces simples
    mesh.add_face([pts[0], pts[1], pts[2], pts[3]])
    mesh.add_face([pts[4], pts[5], pts[6], pts[7]])
    return mesh


def test_drawer_fractional_opening():
    # Cria gaveta simples
    m = _create_box_mesh(0.0, 0.4, 0.0, 0.5, 0.0, 0.2)
    frente = Group(m, name="Balcao - Frente Gaveta 1")
    mod = Group(name="Balcao_1")
    mod.children = [frente]
    mod.ext = {"trazomob_module": {"rot_z": 0.0}}

    # Abertura 50%
    CabinetInteract.set_piece_open_fraction(frente, 0.5, module_group=mod)
    assert frente.ext.get("is_open") is True
    assert frente.ext.get("open_fraction") == 0.5
    # Deslocamento esperado em Y: -0.35 * 0.5 = -0.175
    ys = [v.position.y() for v in frente.mesh.vertices]
    assert min(ys) < -0.10

    # Fechamento (0%)
    CabinetInteract.set_piece_open_fraction(frente, 0.0, module_group=mod)
    assert frente.ext.get("is_open") is False
    assert frente.ext.get("open_fraction") == 0.0
    ys_closed = [v.position.y() for v in frente.mesh.vertices]
    assert abs(min(ys_closed) - 0.0) < 1e-4


def test_door_fractional_opening_and_hinge():
    # Porta esquerda (largura 0.4, altura 0.7, espessura 0.018)
    m = _create_box_mesh(0.0, 0.4, -0.018, 0.0, 0.0, 0.7)
    porta = Group(m, name="Balcao - Porta Esq")
    porta.ext = {"trazomob": {"door_side": "left"}}
    mod = Group(name="Balcao_1")
    mod.children = [porta]
    mod.ext = {"trazomob_module": {"rot_z": 0.0}}

    # 100% de abertura
    CabinetInteract.set_piece_open_fraction(porta, 1.0, module_group=mod)
    assert porta.ext.get("is_open") is True
    # O pivot deve ser próximo a min_x=0.0
    pivot = porta.ext.get("hinge_pivot")
    assert pivot is not None
    assert abs(pivot.x()) < 0.05


def test_collision_detection_between_open_pieces():
    scene = Scene()

    # Módulo A com gaveta abrindo em direção a -Y
    m1 = _create_box_mesh(0.0, 0.4, 0.0, 0.5, 0.0, 0.2)
    gaveta = Group(m1, name="Gaveta_A")
    mod_a = Group(name="Balcao_A")
    mod_a.children = [gaveta]
    mod_a.ext = {"trazomob_module": {"rot_z": 0.0}}

    # Obstáculo na frente da gaveta (ex: puxador de balcão de canto a -0.2m em Y)
    m2 = _create_box_mesh(0.1, 0.3, -0.25, -0.15, 0.0, 0.2)
    obstaculo = Group(m2, name="Puxador_Canto")

    scene.groups.extend([mod_a, obstaculo])

    # Fechada: sem colisão
    CabinetInteract.set_piece_open_fraction(gaveta, 0.0, module_group=mod_a, scene=scene)
    col_closed = check_opening_collisions(scene)
    assert len(col_closed) == 0

    # Aberta 100% (desloca 35cm para a frente -> atinge a zona de Y: -0.35 a 0.15, interceptando o obstáculo)
    CabinetInteract.set_piece_open_fraction(gaveta, 1.0, module_group=mod_a, scene=scene)
    col_open = check_opening_collisions(scene)
    assert len(col_open) > 0
    assert "Gaveta_A" in col_open[0]["desc"]
    assert "Puxador_Canto" in col_open[0]["desc"]
