# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Diálogo 2D de Planta Baixa para desenho de paredes e geração 3D automática."""
from __future__ import annotations

import math
from typing import Optional, List, Tuple

from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import (
    QPainter,
    QPen,
    QColor,
    QBrush,
    QFont,
    QPolygonF,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDoubleSpinBox,
    QCheckBox,
    QFrame,
    QSplitter,
    QToolButton,
    QButtonGroup,
    QInputDialog,
    QComboBox,
    QSlider,
    QFileDialog,
    QGroupBox,
    QScrollArea,
    QMessageBox,
)

from PySide6.QtGui import QVector3D
from core.image_plane import ImagePlane
from core.units import format_length, model_unit, model_precision, bare_number_scale
from ..wall.plan_2d import WallGraph2D, WallNode2D, dist_2d
from ..wall.mesh_builder import WallMeshBuilder



class MeasurementMixin:
    """Logica de medicao e aplicacao de cotas/dimensoes do canvas."""

    def _find_segment_for_dimension(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> Optional[int]:
        """Localiza qual parede é representada ou corre paralela a esses dois pontos cotados."""
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        L = math.hypot(dx, dy)
        if L < 1e-4:
            return None
        ux, uy = dx / L, dy / L

        best_sid = None
        best_score = 999.0

        for sid, seg in self.graph.segments.items():
            na = self.graph.nodes.get(seg.node_a_id)
            nb = self.graph.nodes.get(seg.node_b_id)
            if not na or not nb:
                continue
            sdx = nb.x - na.x
            sdy = nb.y - na.y
            sL = math.hypot(sdx, sdy)
            if sL < 1e-4:
                continue
            sux, suy = sdx / sL, sdy / sL
            # Se forem paralelas
            dot = abs(ux * sux + uy * suy)
            if dot > 0.90:
                # Projeção no eixo perpendicular
                nx, ny = -suy, sux
                perp_dist = abs((p1[0] - na.x) * nx + (p1[1] - na.y) * ny)
                # Projeção no eixo paralelo para verificar sobreposição com o vão
                t1 = (p1[0] - na.x) * sux + (p1[1] - na.y) * suy
                t2 = (p2[0] - na.x) * sux + (p2[1] - na.y) * suy
                min_t, max_t = min(t1, t2), max(t1, t2)
                overlap = max(0.0, min(max_t, sL) - max(min_t, 0.0))
                if overlap > 0.3 * min(L, sL):
                    score = perp_dist
                    if score < best_score:
                        best_score = score
                        best_sid = sid

        return best_sid

    def _edit_custom_dimension_dialog(self, dim_id: int) -> None:
        """Abre diálogo para definir o novo valor da cota criada e redimensiona a parede correspondente."""
        dim = self.graph.dimensions.get(dim_id)
        if not dim:
            return

        scale = bare_number_scale()
        u_name = model_unit()
        p = model_precision()

        cur_dist_m = dist_2d(dim.p1, dim.p2)
        cur_val_doc = cur_dist_m / scale

        val_doc, ok = QInputDialog.getDouble(
            self,
            "Definir Cota",
            f"Comprimento desejado para esta cota ({u_name}):",
            value=round(cur_val_doc, p),
            minValue=0.01,
            maxValue=100000.0,
            decimals=p
        )
        if ok:
            val_m = val_doc * scale
            if abs(val_m - cur_dist_m) > 1e-4:
                diff = val_m - cur_dist_m
                self._save_history()

                # Se a cota ainda não tiver seg_id associado, tenta resolver agora
                if dim.seg_id is None:
                    dim.seg_id = self._find_segment_for_dimension(dim.p1, dim.p2)

                # Se estiver vinculada a uma parede, ajusta o comprimento da parede pelo delta
                if dim.seg_id is not None and dim.seg_id in self.graph.segments:
                    seg = self.graph.segments[dim.seg_id]
                    cur_center_m = seg.length(self.graph)
                    new_center_m = cur_center_m + diff
                    self.graph.set_segment_length(dim.seg_id, new_center_m)
                    self.wall_selected.emit(dim.seg_id, new_center_m)
                else:
                    # Atualiza cota livre não associada a parede
                    dx = dim.p2[0] - dim.p1[0]
                    dy = dim.p2[1] - dim.p1[1]
                    L = math.hypot(dx, dy)
                    if L > 1e-4:
                        ux, uy = dx / L, dy / L
                        dim.p2 = (dim.p1[0] + ux * val_m, dim.p1[1] + uy * val_m)
                self.update()

    def _edit_segment_length_dialog(self, seg_id: int, face_type: str = "centro", current_face_len: Optional[float] = None) -> None:
        """Abre caixa de diálogo para digitar nova medida e atualizar a parede no eixo central."""
        seg = self.graph.segments.get(seg_id)
        if not seg:
            return

        scale = bare_number_scale()
        u_name = model_unit()
        p = model_precision()

        cur_center_m = seg.length(self.graph)
        cur_val_doc = cur_center_m / scale

        val_doc, ok = QInputDialog.getDouble(
            self,
            "Corrigir Medida da Parede",
            f"Novo comprimento da parede ({u_name}):",
            value=round(cur_val_doc, p),
            minValue=0.01,
            maxValue=100000.0,
            decimals=p
        )
        if ok:
            val_m = val_doc * scale
            if abs(val_m - cur_center_m) > 1e-4:
                self._save_history()
                self.graph.set_segment_length(seg_id, val_m)
                self.wall_selected.emit(seg_id, val_m)
                self.update()

    def _apply_typed_length(self, length_m: float) -> None:
        """Aplica o comprimento digitado diretamente pelo teclado e confirma a parede."""
        if length_m <= 0.001:
            return

        # 1. Se houver uma parede selecionada, altera seu comprimento
        if self._selected_seg_id is not None:
            self._save_history()
            self.graph.set_segment_length(self._selected_seg_id, length_m)
            self.wall_selected.emit(self._selected_seg_id, length_m)
            self.update()
            return

        # 2. Se estiver no meio de um traço (_start_pt ativo), cria o segmento na direção do mouse
        # 2. Se estiver posicionando o ponto de partida em T a partir de uma refer?ncia na parede
        if self._start_pt is None and self._t_ref_info is not None:
            ref_pt = self._t_ref_info["ref_pt"]
            u_dir = self._t_ref_info["u_dir"]
            fixed_x = ref_pt[0] + u_dir[0] * length_m
            fixed_y = ref_pt[1] + u_dir[1] * length_m

            # Subdivide imediatamente a parede existente no ponto do T
            self._save_history()
            split_nid = self.graph._get_or_split_at_point(fixed_x, fixed_y, threshold=0.10)
            split_node = self.graph.nodes[split_nid]
            start_coord = (split_node.x, split_node.y)

            # Fixa como in?cio da nova parede e abre a corda el?stica perpendicularmente
            self._start_pt = start_coord
            # Vetor perpendicular ? parede (normal para puxar o T a 90 graus)
            n_perp = (-u_dir[1], u_dir[0])
            self._current_mouse_world = (start_coord[0] + n_perp[0] * 1.0, start_coord[1] + n_perp[1] * 1.0)
            self._t_ref_info = None
            self.wall_count_changed.emit(len(self.graph.segments))
            self.update()
            return

        if self._start_pt is not None:
            p0 = self._start_pt
            p1 = self._current_mouse_world
            dx = p1[0] - p0[0]
            dy = p1[1] - p0[1]
            dist = math.hypot(dx, dy)
            if dist < 1e-4:
                dx, dy = 1.0, 0.0
                dist = 1.0
            ux, uy = dx / dist, dy / dist

            # 1. Se o usu?rio iniciou no canto/marcador da parede e digitou uma dist?ncia ao longo da parede existente
            # (Rastreamento de Ponto de Ramifica??o em T a partir de canto existente):
            start_nid = self.graph.find_node_at(p0[0], p0[1], threshold=0.20)
            colinear_seg = None
            if start_nid is not None:
                for sid, s in self.graph.segments.items():
                    if s.node_a_id == start_nid or s.node_b_id == start_nid:
                        other_id = s.node_b_id if s.node_a_id == start_nid else s.node_a_id
                        other_n = self.graph.nodes.get(other_id)
                        if not other_n:
                            continue
                        sdx = other_n.x - p0[0]
                        sdy = other_n.y - p0[1]
                        s_len = math.hypot(sdx, sdy)
                        if s_len > 1e-4:
                            dot = (sdx / s_len) * ux + (sdy / s_len) * uy
                            # Se o mouse est? apontando ao longo da parede existente e a dist?ncia digitada est? dentro dela
                            if dot > 0.90 and 0.01 < length_m < s_len:
                                colinear_seg = s
                                break

            if colinear_seg is not None:
                # O usu?rio quis posicionar o T a partir do canto digitando a dist?ncia!
                fixed_x = p0[0] + ux * length_m
                fixed_y = p0[1] + uy * length_m
                self._save_history()
                split_nid = self.graph._get_or_split_at_point(fixed_x, fixed_y, threshold=0.10)
                split_node = self.graph.nodes[split_nid]
                start_coord = (split_node.x, split_node.y)

                # Fixa _start_pt exatamente no ponto do T e abre a corda el?stica perpendicular ? parede existente!
                self._start_pt = start_coord
                n_perp = (-uy, ux)
                self._current_mouse_world = (start_coord[0] + n_perp[0] * 1.0, start_coord[1] + n_perp[1] * 1.0)
                self.wall_count_changed.emit(len(self.graph.segments))
                self.update()
                return

            ext = self.graph.get_start_extension(p0, (ux, uy))
            eff_len = length_m + ext
            end_x = p0[0] + ux * eff_len
            end_y = p0[1] + uy * eff_len

            self._save_history()
            self.graph.add_segment(p0[0], p0[1], end_x, end_y)
            self.graph.merge_close_nodes(threshold=0.25)
            self.wall_count_changed.emit(len(self.graph.segments))

            # Verifica se fechou um ciclo
            end_nid = self.graph.find_node_at(end_x, end_y, threshold=0.25)
            deg = 0
            if end_nid is not None:
                deg = sum(1 for s in self.graph.segments.values() if s.node_a_id == end_nid or s.node_b_id == end_nid)

            if deg >= 2:
                self._start_pt = None
            else:
                self._start_pt = (end_x, end_y)

            self.update()

