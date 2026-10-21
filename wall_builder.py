# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Construtor Interativo de Paredes (Wall Builder) para Design de Interiores.

Permite desenhar paredes contínuas no viewport com cantos em esquadria (miter corners)
perfeitamente fechados e alinhados, pé-direito, espessura e alinhamento configuráveis,
gerando geometria 3D sólida (manifold), limpa e agrupada automaticamente na camada "Paredes"
(e piso na camada "Piso" ao fechar o ciclo).
"""
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QVector3D

from core.group import Group
from core.history import Command
from core.layers import Layer
from core.mesh import Mesh
from core.triangulate import triangulate
from tools.base import Tool, ToolContext


from .wall_mesh_builder import line_intersection_2d, WallMeshBuilder


class AddWallGroupCommand(Command):
    """Comando reversível (Undo/Redo) para inserção de paredes contínuas."""

    def __init__(self, group: Group) -> None:
        self.group = group

    def do(self, scene) -> None:
        if self.group not in scene.groups:
            scene.groups.append(self.group)
        scene.version += 1

    def undo(self, scene) -> None:
        if self.group in scene.groups:
            scene.groups.remove(self.group)
        scene.version += 1


class ReplaceWallGroupCommand(Command):
    """Comando reversível para atualizar o sólido da parede contínua ao estender a cadeia."""

    def __init__(self, old_group: Optional[Group], new_group: Group) -> None:
        self.old_group = old_group
        self.new_group = new_group

    def do(self, scene) -> None:
        if self.old_group is not None and self.old_group in scene.groups:
            idx = scene.groups.index(self.old_group)
            scene.groups[idx] = self.new_group
        else:
            scene.groups.append(self.new_group)
        scene.version += 1

    def undo(self, scene) -> None:
        if self.new_group in scene.groups:
            if self.old_group is not None:
                idx = scene.groups.index(self.new_group)
                scene.groups[idx] = self.old_group
            else:
                scene.groups.remove(self.new_group)
        scene.version += 1


class AddFloorCommand(Command):
    """Comando reversível para inserção de piso ao fechar o perímetro de paredes."""

    def __init__(self, group: Group) -> None:
        self.group = group

    def do(self, scene) -> None:
        if self.group not in scene.groups:
            scene.groups.append(self.group)
        scene.version += 1

    def undo(self, scene) -> None:
        if self.group in scene.groups:
            scene.groups.remove(self.group)
        scene.version += 1


class WallBuilderTool(Tool):
    """Ferramenta interativa de desenho de paredes no padrão de design de interiores."""

    name = "Construtor de Paredes"
    shortcut = "W"
    description = "Clique para posicionar cantos de paredes contínuas; digite o comprimento ou feche o ciclo."
    vcb_label = "Comprimento"
    uses_snap = True
    magnetic_axis_deg = 4.0
    screen_axis_px = 12.0

    def __init__(
        self,
        altura_m: float = 2.60,
        espessura_m: float = 0.15,
        alinhamento: str = "interno",
        gerar_teto: bool = False,
        on_wall_added=None,
        on_deactivated=None,
    ) -> None:
        super().__init__()
        self.altura_m = altura_m
        self.espessura_m = espessura_m
        # "interno" (referência na face interna), "centro", "externo"
        self.alinhamento = alinhamento
        self.gerar_teto = gerar_teto
        self.on_wall_added = on_wall_added
        self.on_deactivated = on_deactivated

        self.start_point: Optional[QVector3D] = None
        self.hover_point: Optional[QVector3D] = None
        self.chain_first_point: Optional[QVector3D] = None
        self.chain_points: list[QVector3D] = []
        self._current_wall_group: Optional[Group] = None
        self._wall_counter = 1

    def set_params(self, altura_m: float, espessura_m: float, alinhamento: str, gerar_teto: Optional[bool] = None) -> None:
        self.altura_m = altura_m
        self.espessura_m = espessura_m
        self.alinhamento = alinhamento
        if gerar_teto is not None:
            self.gerar_teto = bool(gerar_teto)

    def on_activate(self, viewport) -> None:
        self._reset()
        if hasattr(viewport, "status_message"):
            viewport.status_message(
                f"🧱 Construtor de Paredes Ativo: Altura={self.altura_m:.2f}m, Espessura={self.espessura_m*100:.0f}cm. Clique para iniciar."
            )

    def on_deactivate(self, viewport) -> None:
        self._reset()
        self.hover_point = None
        if callable(self.on_deactivated):
            self.on_deactivated()

    def _reset(self) -> None:
        self.start_point = None
        self.chain_first_point = None
        self.chain_points.clear()
        self._current_wall_group = None

    def on_cancel(self, viewport) -> None:
        self._reset()
        viewport.update()

    def on_hover(self, ctx: ToolContext) -> None:
        pt = ctx.world
        self.hover_point = QVector3D(pt.x(), pt.y(), 0.0)
        ctx.viewport.update()

    def on_click(self, ctx: ToolContext) -> None:
        clicked = QVector3D(ctx.world.x(), ctx.world.y(), 0.0)

        # 1. Primeiro clique: define início da cadeia de paredes
        if self.start_point is None:
            self.start_point = clicked
            self.chain_first_point = clicked
            self.chain_points = [clicked]
            self._current_wall_group = None
            ctx.viewport.update()
            return

        # Distância mínima para evitar ponto duplicado no mesmo local
        delta = clicked - self.start_point
        if delta.length() < 0.02:
            return

        # 2. Verificar se fechou o ciclo clicando próximo ao ponto inicial
        is_closing = False
        if self.chain_first_point is not None and len(self.chain_points) >= 2:
            dist_to_first = (clicked - self.chain_first_point).length()
            if dist_to_first < max(0.20, self.espessura_m * 1.5):
                clicked = self.chain_first_point
                is_closing = True

        pts_for_build = list(self.chain_points)
        if not is_closing:
            pts_for_build.append(clicked)

        # Constrói o sólido contínuo com cantos em esquadria (miter) fechados
        new_grp = self.build_chain_group(
            scene=ctx.viewport.scene,
            pts=pts_for_build,
            is_closed=is_closing,
            altura_m=self.altura_m,
            espessura_m=self.espessura_m,
            alinhamento=self.alinhamento,
            name_override=self._current_wall_group.name if self._current_wall_group else None,
        )

        cmd = ReplaceWallGroupCommand(self._current_wall_group, new_grp)
        ctx.viewport.history.execute(cmd)
        self._current_wall_group = new_grp

        if self.on_wall_added:
            self.on_wall_added(new_grp)

        if is_closing:
            # Gerar automaticamente o piso delimitado pelos cantos internos
            floor_cmd = self._build_floor(ctx.viewport.scene, self.chain_points)
            if floor_cmd is not None:
                ctx.viewport.history.execute(floor_cmd)

            # Gerar automaticamente o teto no pé-direito se configurado
            created_teto = False
            if getattr(self, "gerar_teto", False):
                alt = self.altura_m[0] if isinstance(self.altura_m, (list, tuple)) else float(self.altura_m)
                ceiling_cmd = self._build_ceiling(ctx.viewport.scene, self.chain_points, altura_m=alt)
                if ceiling_cmd is not None:
                    ctx.viewport.history.execute(ceiling_cmd)
                    created_teto = True

            if hasattr(ctx.viewport, "flash_status"):
                msg = "🧱 Parede, piso e teto criados com sucesso!" if created_teto else "🧱 Perímetro de paredes e piso criados com sucesso!"
                ctx.viewport.flash_status(msg)

            self._reset()
        else:
            self.chain_points.append(clicked)
            self.start_point = clicked

        ctx.viewport.update()

    def on_value(self, viewport, value) -> bool:
        """Suporte a digitação direta da medida na caixa de medição (VCB)."""
        if self.start_point is None or self.hover_point is None:
            return False

        direction = self.hover_point - self.start_point
        dist = direction.length()
        if dist < 1e-4:
            return False

        if isinstance(value, (int, float)):
            length_m = float(value)
            # Se digitou em mm (> 50), converte para m
            if length_m > 50.0:
                length_m /= 1000.0
            new_target = self.start_point + direction.normalized() * length_m
            new_target.setZ(0.0)

            pts_for_build = list(self.chain_points) + [new_target]
            new_grp = self.build_chain_group(
                scene=viewport.scene,
                pts=pts_for_build,
                is_closed=False,
                altura_m=self.altura_m,
                espessura_m=self.espessura_m,
                alinhamento=self.alinhamento,
                name_override=self._current_wall_group.name if self._current_wall_group else None,
            )

            cmd = ReplaceWallGroupCommand(self._current_wall_group, new_grp)
            viewport.history.execute(cmd)
            self._current_wall_group = new_grp

            if self.on_wall_added:
                self.on_wall_added(new_grp)

            self.chain_points.append(new_target)
            self.start_point = new_target
            viewport.update()
            return True

        return False

    def rubber_band_lines(self):
        """Desenha a prévia dinâmica da parede e de sua espessura enquanto o mouse se move."""
        if self.start_point is None or self.hover_point is None:
            return []

        p0 = self.start_point
        p1 = self.hover_point
        direction = p1 - p0
        dist = direction.length()
        if dist < 1e-4:
            return []

        dir_norm = direction.normalized()
        perp = QVector3D(-dir_norm.y(), dir_norm.x(), 0.0).normalized()

        esp = self.espessura_m
        if self.alinhamento == "interno":
            offset_a = QVector3D(0, 0, 0)
            offset_b = perp * esp
        elif self.alinhamento == "externo":
            offset_a = -perp * esp
            offset_b = QVector3D(0, 0, 0)
        else:  # centro
            offset_a = -perp * (esp / 2.0)
            offset_b = perp * (esp / 2.0)

        # 4 cantos no piso
        c0 = p0 + offset_a
        c1 = p1 + offset_a
        c2 = p1 + offset_b
        c3 = p0 + offset_b

        alt_vec = QVector3D(0, 0, self.altura_m)

        lines = [
            # Base
            (c0, c1), (c1, c2), (c2, c3), (c3, c0),
            # Linha guia central de clique
            (p0, p1),
            # Colunas verticais
            (c0, c0 + alt_vec), (c1, c1 + alt_vec),
            (c2, c2 + alt_vec), (c3, c3 + alt_vec),
            # Topo
            (c0 + alt_vec, c1 + alt_vec),
            (c1 + alt_vec, c2 + alt_vec),
            (c2 + alt_vec, c3 + alt_vec),
            (c3 + alt_vec, c0 + alt_vec),
        ]

        # Se estiver perto do ponto inicial, destaca fechamento
        if self.chain_first_point is not None and len(self.chain_points) >= 2:
            dist_to_first = (p1 - self.chain_first_point).length()
            if dist_to_first < max(0.25, self.espessura_m * 1.5):
                lines.append((p1, self.chain_first_point))

        return lines

    def draw_overlay(self, viewport, painter: QPainter) -> None:
        """Renderiza a cota visual interativa (linha de cota, setas e etiqueta de metragem)

        em tempo real durante o desenho da parede.
        """
        if self.start_point is None or self.hover_point is None:
            return

        p0 = self.start_point
        p1 = self.hover_point
        dist_m = (p1 - p0).length()
        if dist_m < 0.05:
            return

        # Converte pontos 3D do chão para pixels da tela 2D
        p0_px = viewport._world_to_pixel(p0)
        p1_px = viewport._world_to_pixel(p1)
        if p0_px is None or p1_px is None:
            return

        x0, y0 = p0_px
        x1, y1 = p1_px
        dx = x1 - x0
        dy = y1 - y0
        screen_len = math.hypot(dx, dy)
        if screen_len < 10.0:
            return

        ux = dx / screen_len
        uy = dy / screen_len
        # Vetor normal perpendicular à linha na tela (deslocamento para o lado da cota)
        nx = -uy
        ny = ux
        offset_px = 24.0

        # Pontos da linha principal de cota
        cx0 = x0 + nx * offset_px
        cy0 = y0 + ny * offset_px
        cx1 = x1 + nx * offset_px
        cy1 = y1 + ny * offset_px

        painter.save()
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.TextAntialiasing, True)

            # 1. Linhas de extensão / testemunhas (finas e discretas)
            pen_ext = QPen(QColor(120, 140, 160, 160), 1.0, Qt.DashLine)
            painter.setPen(pen_ext)
            painter.drawLine(QPointF(x0 + nx * 4.0, y0 + ny * 4.0), QPointF(cx0 + nx * 5.0, cy0 + ny * 5.0))
            painter.drawLine(QPointF(x1 + nx * 4.0, y1 + ny * 4.0), QPointF(cx1 + nx * 5.0, cy1 + ny * 5.0))

            # 2. Linha de cota com cor de destaque vibrante (azul elétrico / ciano)
            cota_color = QColor(0, 140, 255)
            pen_cota = QPen(cota_color, 1.8)
            painter.setPen(pen_cota)
            painter.drawLine(QPointF(cx0, cy0), QPointF(cx1, cy1))

            # 3. Setas nas extremidades
            arrow_len = min(10.0, screen_len * 0.25)
            arrow_width = 3.5
            for tip_x, tip_y, sgn in ((cx0, cy0, 1.0), (cx1, cy1, -1.0)):
                wing1_x = tip_x + (ux * sgn) * arrow_len + nx * arrow_width
                wing1_y = tip_y + (uy * sgn) * arrow_len + ny * arrow_width
                wing2_x = tip_x + (ux * sgn) * arrow_len - nx * arrow_width
                wing2_y = tip_y + (uy * sgn) * arrow_len - ny * arrow_width
                painter.drawLine(QPointF(tip_x, tip_y), QPointF(wing1_x, wing1_y))
                painter.drawLine(QPointF(tip_x, tip_y), QPointF(wing2_x, wing2_y))

            # 4. Etiqueta / Badge com as medidas em mm e metros
            dist_mm = int(round(dist_m * 1000.0))
            texto = f"{dist_mm} mm ({dist_m:.2f} m)"

            font = QFont()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(texto)
            th = fm.height()

            # Ponto médio da cota
            mid_x = (cx0 + cx1) / 2.0
            mid_y = (cy0 + cy1) / 2.0

            pad_x, pad_y = 7, 4
            badge_rect = QRectF(
                mid_x - tw / 2.0 - pad_x,
                mid_y - th / 2.0 - pad_y,
                tw + pad_x * 2,
                th + pad_y * 2,
            )

            # Fundo escuro translúcido com borda suave
            painter.setPen(QPen(cota_color, 1.2))
            painter.setBrush(QColor(24, 28, 36, 220))
            painter.drawRoundedRect(badge_rect, 5.0, 5.0)

            # Texto nítido em branco
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(badge_rect, Qt.AlignCenter, texto)

        finally:
            painter.restore()

    @classmethod
    def build_chain_group(
        cls,
        scene,
        pts: list[QVector3D],
        is_closed: bool,
        altura_m: float | list[float],
        espessura_m: float,
        alinhamento: str = "interno",
        name_override: Optional[str] = None,
        segment_index: Optional[int] = None,
    ) -> Group:
        """Constrói uma parede contínua única (manifold sólida), com cantos unidos em esquadria."""
        n_pts = len(pts)
        n_segs = n_pts if is_closed else max(0, n_pts - 1)

        if isinstance(altura_m, (int, float)):
            alturas_list = [float(altura_m)] * n_segs
        else:
            alturas_list = [float(h) for h in altura_m]
            if len(alturas_list) < n_segs:
                last_h = alturas_list[-1] if alturas_list else 2.6
                alturas_list.extend([last_h] * (n_segs - len(alturas_list)))
            elif len(alturas_list) > n_segs:
                alturas_list = alturas_list[:n_segs]

        mesh, face_map = cls.compute_wall_mesh(pts, is_closed, alturas_list, espessura_m, alinhamento)

        layer_name = "Parede"
        if scene is not None and scene.layer(layer_name) is None:
            scene.layers.append(Layer(layer_name))

        name = name_override or "Parede Contínua"

        # Guarda metadados paramétricos no container para permitir edição dinâmica
        pts_serialized = [[p.x(), p.y(), p.z()] for p in pts]
        ext_data = {
            "trazomob_wall": {
                "pontos": pts_serialized,
                "is_closed": bool(is_closed),
                "altura": float(alturas_list[0]) if alturas_list else 2.6,
                "alturas": [float(h) for h in alturas_list],
                "espessura": float(espessura_m),
                "alinhamento": str(alinhamento),
                "selected_segment": segment_index,
                "face_segment_map": face_map,
            },
            "motion_locked": True,
        }

        grp = Group(mesh, name=name)
        grp.layer = layer_name
        grp.ext = ext_data
        return grp

    @classmethod
    def compute_wall_mesh(
        cls,
        pts: list[QVector3D],
        is_closed: bool,
        altura_m: float | list[float],
        espessura_m: float,
        alinhamento: str = "interno",
    ) -> tuple[Mesh, dict[int, int]]:
        """Delega o calculo da malha 3D de paredes para o WallMeshBuilder."""
        return WallMeshBuilder.compute_wall_mesh(pts, is_closed, altura_m, espessura_m, alinhamento)

    def _build_floor(self, scene, points: list[QVector3D]) -> Optional[AddFloorCommand]:
        """Delega a geracao do solido do piso para o WallMeshBuilder."""
        grp = WallMeshBuilder.build_floor_group(scene, points)
        return AddFloorCommand(grp) if grp is not None else None

    def _build_ceiling(self, scene, points: list[QVector3D], altura_m: float = 2.60) -> Optional[AddFloorCommand]:
        """Delega a geracao do solido do teto para o WallMeshBuilder."""
        grp = WallMeshBuilder.build_ceiling_group(scene, points, altura_m=altura_m)
        return AddFloorCommand(grp) if grp is not None else None

