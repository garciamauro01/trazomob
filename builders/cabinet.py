# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Construtor parametrico 3D de armarios e chapas de MDF (CabinetBuilder)."""
from __future__ import annotations

from PySide6.QtGui import QVector3D

from core.group import Group
from core.history import Command

from ..builders.mesh_utils import _make_board_mesh, create_board_group

from .cabinet_caixa import CaixaMixin
from .cabinet_delegates import DelegatesMixin
from .cabinet_module_group import ModuleGroupMixin
from .cabinet_transform import CabinetTransformMixin

__all__ = [
    "CabinetBuilder",
    "RotateTrazoMobModuleCommand",
    "_make_board_mesh",
    "create_board_group",
]


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



class CabinetBuilder(
    DelegatesMixin,
    ModuleGroupMixin,
    CaixaMixin,
    CabinetTransformMixin,
):
    """Gera modulos dinamicos e suas pecas componentes."""
