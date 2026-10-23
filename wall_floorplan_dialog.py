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
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
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
)

from .wall_plan_2d import WallGraph2D, dist_2d


class WallFloorplanCanvas(QWidget):
    """Canvas 2D interativo com grid, zoom, pan e cotas dinâmicas em tempo real."""

    wall_count_changed = Signal(int)

    def __init__(self, graph: WallGraph2D, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.graph = graph
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Visualização (Pan & Zoom)
        self._zoom = 80.0  # pixels por metro (80px = 1.0m)
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._pan_start: Optional[QPointF] = None

        # Ferramenta ativa: "linha", "retangulo" ou "selecionar"
        self.mode = "linha"

        # Estado de desenho
        self._start_pt: Optional[Tuple[float, float]] = None
        self._current_mouse_world: Tuple[float, float] = (0.0, 0.0)
        self._snap_info: Optional[str] = None
        self._history: List[List[Tuple[float, float, float, float]]] = []

        # Estado de seleção e arrasto
        self._selected_seg_id: Optional[int] = None
        self._selected_node_id: Optional[int] = None
        self._drag_node_id: Optional[int] = None
        self._drag_start_mouse: Optional[Tuple[float, float]] = None
        self._dimension_badges: Dict[int, QRectF] = {}  # {seg_id: rect_screen} para duplo clique


    def reset_view(self) -> None:
        self._offset_x = self.width() / 2.0
        self._offset_y = self.height() / 2.0
        self._zoom = 80.0
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._offset_x == 0.0 and self._offset_y == 0.0:
            self._offset_x = self.width() / 2.0
            self._offset_y = self.height() / 2.0

    def world_to_screen(self, wx: float, wy: float) -> QPointF:
        sx = self._offset_x + wx * self._zoom
        sy = self._offset_y - wy * self._zoom  # Inverte eixo Y para padrão CAD (+Y para cima)
        return QPointF(sx, sy)

    def screen_to_world(self, sx: float, sy: float) -> Tuple[float, float]:
        wx = (sx - self._offset_x) / self._zoom
        wy = -(sy - self._offset_y) / self._zoom
        return wx, wy

    def _save_history(self) -> None:
        snapshot = []
        for seg in self.graph.segments.values():
            na = self.graph.nodes[seg.node_a_id]
            nb = self.graph.nodes[seg.node_b_id]
            snapshot.append((na.x, na.y, nb.x, nb.y))
        self._history.append(snapshot)

    def undo(self) -> bool:
        if not self._history:
            if self._start_pt is not None:
                self._start_pt = None
                self.update()
                return True
            return False

        last_state = self._history.pop()
        self.graph.clear()
        for x1, y1, x2, y2 in last_state:
            self.graph.add_segment(x1, y1, x2, y2)
        self._start_pt = None
        self.wall_count_changed.emit(len(self.graph.segments))
        self.update()
        return True

    def clear_all(self) -> None:
        self._save_history()
        self.graph.clear()
        self._start_pt = None
        self.wall_count_changed.emit(0)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier):
            self._pan_start = event.position()
            return

        if event.button() == Qt.RightButton:
            # Cancela desenho atual ou desfaz seleção
            if self._start_pt is not None:
                self._start_pt = None
            self._selected_seg_id = None
            self._selected_node_id = None
            self._drag_node_id = None
            self.update()
            return

        if event.button() == Qt.LeftButton:
            wx, wy = self.screen_to_world(event.position().x(), event.position().y())

            # Se estiver no modo selecionar ou clicar em um nó/parede:
            if self.mode == "selecionar":
                hit_node = self.graph.find_node_at(wx, wy, threshold=0.25)
                if hit_node is not None:
                    self._selected_node_id = hit_node
                    self._selected_seg_id = None
                    self._drag_node_id = hit_node
                    self._drag_start_mouse = (wx, wy)
                    self._save_history()
                    self.update()
                    return

                hit_seg = self.graph.find_segment_at(wx, wy, threshold=0.25)
                if hit_seg is not None:
                    self._selected_seg_id = hit_seg
                    self._selected_node_id = None
                    self.update()
                    return

                # Clicou no vazio: desmarca
                self._selected_node_id = None
                self._selected_seg_id = None
                self.update()
                return

            # Modo de desenho ("linha" ou "retangulo")
            # Aplica snap
            wx, wy, _ = self.graph.snap_point(wx, wy, threshold=0.25)

            # Snap ortogonal a 90 graus se shift ou se próximo
            if self._start_pt is not None:
                wx, wy = self._ortho_align(self._start_pt, (wx, wy), force_ortho=bool(event.modifiers() & Qt.ShiftModifier))

            if self.mode == "linha":
                if self._start_pt is None:
                    self._start_pt = (wx, wy)
                else:
                    self._save_history()
                    self.graph.add_segment(self._start_pt[0], self._start_pt[1], wx, wy)
                    self._start_pt = (wx, wy)  # Continua desenhando a próxima parede conectada
                    self.wall_count_changed.emit(len(self.graph.segments))
            elif self.mode == "retangulo":
                if self._start_pt is None:
                    self._start_pt = (wx, wy)
                else:
                    self._save_history()
                    x0, y0 = self._start_pt
                    x1, y1 = wx, wy
                    self.graph.add_segment(x0, y0, x1, y0)
                    self.graph.add_segment(x1, y0, x1, y1)
                    self.graph.add_segment(x1, y1, x0, y1)
                    self.graph.add_segment(x0, y1, x0, y0)
                    self._start_pt = None
                    self.wall_count_changed.emit(len(self.graph.segments))

            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Duplo clique em uma cota ou parede para editar a medida numericamente."""
        click_pos = event.position()
        target_seg_id = None

        # 1. Checa se clicou no badge de cota
        for sid, rect in self._dimension_badges.items():
            if rect.contains(click_pos):
                target_seg_id = sid
                break

        # 2. Se não clicou no badge, checa se clicou próximo de alguma parede
        if target_seg_id is None:
            wx, wy = self.screen_to_world(click_pos.x(), click_pos.y())
            target_seg_id = self.graph.find_segment_at(wx, wy, threshold=0.30)

        if target_seg_id is not None:
            self._edit_segment_length_dialog(target_seg_id)

    def _edit_segment_length_dialog(self, seg_id: int) -> None:
        """Abre caixa de diálogo para digitar nova medida e atualizar a parede."""
        seg = self.graph.segments.get(seg_id)
        if not seg:
            return

        cur_len = seg.length(self.graph)
        val, ok = QInputDialog.getDouble(
            self,
            "Corrigir Medida da Parede",
            f"Digite o novo comprimento da parede (metros):",
            value=round(cur_len, 2),
            minValue=0.10,
            maxValue=50.0,
            decimals=2
        )
        if ok and abs(val - cur_len) > 1e-4:
            self._save_history()
            self.graph.set_segment_length(seg_id, val)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pan_start is not None:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self._offset_x += delta.x()
            self._offset_y += delta.y()
            self.update()
            return

        wx, wy = self.screen_to_world(event.position().x(), event.position().y())

        # Se estiver arrastando um nó (ex: junção em T ou canto de parede):
        if self._drag_node_id is not None:
            # Aplica snap ortogonal ou de grid se shift estiver pressionado
            if bool(event.modifiers() & Qt.ShiftModifier) and self._drag_start_mouse:
                wx, wy = self._ortho_align(self._drag_start_mouse, (wx, wy), force_ortho=True)
            self.graph.move_node(self._drag_node_id, wx, wy)
            self._current_mouse_world = (wx, wy)
            self.update()
            return

        wx, wy, snap_type = self.graph.snap_point(wx, wy, threshold=0.25)
        self._snap_info = snap_type

        if self._start_pt is not None:
            wx, wy = self._ortho_align(self._start_pt, (wx, wy), force_ortho=bool(event.modifiers() & Qt.ShiftModifier))

        self._current_mouse_world = (wx, wy)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self._pan_start is not None):
            self._pan_start = None

        if event.button() == Qt.LeftButton and self._drag_node_id is not None:
            self._drag_node_id = None
            self._drag_start_mouse = None
            self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1.0 / 1.15

        # Zoom centrado no mouse
        mouse_pos = event.position()
        wx, wy = self.screen_to_world(mouse_pos.x(), mouse_pos.y())

        self._zoom = max(10.0, min(1000.0, self._zoom * factor))
        self._offset_x = mouse_pos.x() - wx * self._zoom
        self._offset_y = mouse_pos.y() + wy * self._zoom
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self._start_pt = None
            self._selected_node_id = None
            self._selected_seg_id = None
            self._drag_node_id = None
            self.update()
        elif event.key() == Qt.Key_Delete and self._selected_seg_id is not None:
            # Exclui segmento selecionado
            self._save_history()
            del self.graph.segments[self._selected_seg_id]
            self._selected_seg_id = None
            self.wall_count_changed.emit(len(self.graph.segments))
            self.update()
        elif event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            self.undo()
        else:
            super().keyPressEvent(event)

    def _ortho_align(self, p0: Tuple[float, float], p1: Tuple[float, float], force_ortho: bool = False) -> Tuple[float, float]:
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        dist = math.hypot(dx, dy)
        if dist < 0.05:
            return p1

        angle = math.degrees(math.atan2(dy, dx))
        tol = 12.0
        if force_ortho or abs(angle) <= tol or abs(abs(angle) - 180.0) <= tol:
            return (p1[0], p0[1])
        elif force_ortho or abs(abs(angle) - 90.0) <= tol:
            return (p0[0], p1[1])
        return p1

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Fundo escuro estilo CAD / TrazoMob
        painter.fillRect(self.rect(), QColor(24, 28, 36))

        # 1. Desenha Grid Métrico
        self._draw_grid(painter)

        # 2. Desenha Paredes Existentes
        self._draw_walls(painter)

        # 3. Desenha Prévia do que está sendo desenhado (Borracha elástica / Rubberband)
        self._draw_rubberband(painter)

        # 4. Indicador de Snap
        self._draw_snap_marker(painter)

    def _draw_grid(self, painter: QPainter) -> None:
        w = self.width()
        h = self.height()

        grid_spacing_m = 1.0 if self._zoom < 60.0 else 0.5
        spacing_px = grid_spacing_m * self._zoom

        x_start = self._offset_x % spacing_px
        y_start = self._offset_y % spacing_px

        pen_grid = QPen(QColor(42, 48, 60), 0.8)
        painter.setPen(pen_grid)

        x = x_start
        while x < w:
            painter.drawLine(QPointF(x, 0), QPointF(x, h))
            x += spacing_px

        y = y_start
        while y < h:
            painter.drawLine(QPointF(0, y), QPointF(w, y))
            y += spacing_px

        # Eixos principais (Origem 0,0)
        orig = self.world_to_screen(0.0, 0.0)
        painter.setPen(QPen(QColor(230, 80, 80, 140), 1.2))
        painter.drawLine(QPointF(0, orig.y()), QPointF(w, orig.y()))  # Eixo X
        painter.setPen(QPen(QColor(80, 200, 120, 140), 1.2))
        painter.drawLine(QPointF(orig.x(), 0), QPointF(orig.x(), h))  # Eixo Y

    def _draw_walls(self, painter: QPainter) -> None:
        polys = self.graph.compute_wall_polygons()
        self._dimension_badges.clear()

        # Mapeia quais nós têm 2 paredes formando canto
        node_segments: Dict[int, List[int]] = {nid: [] for nid in self.graph.nodes}
        for seg_id, seg in self.graph.segments.items():
            node_segments[seg.node_a_id].append(seg_id)
            node_segments[seg.node_b_id].append(seg_id)

        # 1. As linhas de borda de cada parede com cantos chanfrados / miter a 45°
        pen_border = QPen(QColor(230, 235, 245), 1.6, Qt.SolidLine)
        pen_border.setCapStyle(Qt.RoundCap)
        pen_border.setJoinStyle(Qt.MiterJoin)

        pen_selected = QPen(QColor(255, 214, 0), 2.2, Qt.SolidLine)
        pen_selected.setCapStyle(Qt.RoundCap)
        pen_selected.setJoinStyle(Qt.MiterJoin)

        for seg_id, quad in polys.items():
            # Se selecionado, destaca em amarelo dourado
            painter.setPen(pen_selected if seg_id == self._selected_seg_id else pen_border)

            # quad = (c0, c1, c2, c3) em coordenadas de mundo
            s0 = self.world_to_screen(quad[0][0], quad[0][1])
            s1 = self.world_to_screen(quad[1][0], quad[1][1])
            s2 = self.world_to_screen(quad[2][0], quad[2][1])
            s3 = self.world_to_screen(quad[3][0], quad[3][1])

            # Linha lateral esquerda (c0 -> c1)
            painter.drawLine(s0, s1)
            # Linha lateral direita (c2 -> c3)
            painter.drawLine(s2, s3)

            # Se a extremidade A for livre (1 único segmento no nó), fecha a ponta
            seg = self.graph.segments[seg_id]
            if len(node_segments.get(seg.node_a_id, [])) == 1:
                painter.drawLine(s3, s0)
            # Se a extremidade B for livre, fecha a ponta
            if len(node_segments.get(seg.node_b_id, [])) == 1:
                painter.drawLine(s1, s2)

        # 2. Fecha os cantos em 45 graus (Linha de junta / miter do canto da parede)
        pen_miter = QPen(QColor(230, 235, 245, 200), 1.4, Qt.SolidLine)
        painter.setPen(pen_miter)

        for nid, seg_ids in node_segments.items():
            if len(seg_ids) == 2:
                # Canto L com 2 paredes: une o ponto interno ao externo na linha de 45°
                s_a = seg_ids[0]
                q_a = polys.get(s_a)
                if not q_a:
                    continue
                seg_a_obj = self.graph.segments[s_a]
                if seg_a_obj.node_a_id == nid:
                    # No nó nid, os cantos correspondentes deste segmento são q_a[0] e q_a[3]
                    p_miter1 = self.world_to_screen(q_a[0][0], q_a[0][1])
                    p_miter2 = self.world_to_screen(q_a[3][0], q_a[3][1])
                else:
                    # No nó nid, os cantos correspondentes deste segmento são q_a[1] e q_a[2]
                    p_miter1 = self.world_to_screen(q_a[1][0], q_a[1][1])
                    p_miter2 = self.world_to_screen(q_a[2][0], q_a[2][1])
                painter.drawLine(p_miter1, p_miter2)

        # 3. Coluna separando paredes em junções em T (ou X)
        columns = self.graph.compute_columns()
        pen_column = QPen(QColor(245, 180, 70), 1.6, Qt.SolidLine)
        brush_column = QBrush(QColor(40, 32, 20, 180))
        pen_hatch = QPen(QColor(245, 180, 70, 160), 1.0, Qt.SolidLine)

        for nid, col_quad in columns.items():
            s0 = self.world_to_screen(col_quad[0][0], col_quad[0][1])
            s1 = self.world_to_screen(col_quad[1][0], col_quad[1][1])
            s2 = self.world_to_screen(col_quad[2][0], col_quad[2][1])
            s3 = self.world_to_screen(col_quad[3][0], col_quad[3][1])

            # Desenha o contorno preenchido da coluna
            from PySide6.QtGui import QPolygonF
            poly = QPolygonF([s0, s1, s2, s3])
            painter.setPen(pen_column)
            painter.setBrush(brush_column)
            painter.drawPolygon(poly)

            # Hachura em 'X' padrão arquitetural para pilar / coluna estrutural
            painter.setPen(pen_hatch)
            painter.drawLine(s0, s2)
            painter.drawLine(s1, s3)

            # Fecha a extremidade de cada parede que chega a esta coluna (tampa de encosto)
            pen_cap = QPen(QColor(230, 235, 245), 1.4, Qt.SolidLine)
            painter.setPen(pen_cap)
            for sid in node_segments.get(nid, []):
                q = polys.get(sid)
                if not q:
                    continue
                s_obj = self.graph.segments[sid]
                if s_obj.node_a_id == nid:
                    # Extremidade A encostando na coluna: liga c3 e c0
                    pa = self.world_to_screen(q[3][0], q[3][1])
                    pb = self.world_to_screen(q[0][0], q[0][1])
                else:
                    # Extremidade B encostando na coluna: liga c1 e c2
                    pa = self.world_to_screen(q[1][0], q[1][1])
                    pb = self.world_to_screen(q[2][0], q[2][1])
                painter.drawLine(pa, pb)

        # 4. Linha de eixo central (tracejada fina azul) e cotas de comprimento
        pen_center = QPen(QColor(70, 140, 245, 180), 1.0, Qt.DashLine)
        painter.setPen(pen_center)
        for sid, seg in self.graph.segments.items():
            na = self.graph.nodes[seg.node_a_id]
            nb = self.graph.nodes[seg.node_b_id]
            
            # Pega os centros das pontas a partir do quad da parede (já ajustado para a face da coluna)
            q = polys.get(sid)
            if q:
                # Ponta A é o ponto médio de (c0, c3)
                p0_w = ((q[0][0] + q[3][0]) / 2.0, (q[0][1] + q[3][1]) / 2.0)
                # Ponta B é o ponto médio de (c1, c2)
                p1_w = ((q[1][0] + q[2][0]) / 2.0, (q[1][1] + q[2][1]) / 2.0)
                p0 = self.world_to_screen(p0_w[0], p0_w[1])
                p1 = self.world_to_screen(p1_w[0], p1_w[1])
            else:
                p0 = self.world_to_screen(na.x, na.y)
                p1 = self.world_to_screen(nb.x, nb.y)
            painter.drawLine(p0, p1)

            # Cota de comprimento interativa com registro para duplo clique
            length_m = dist_2d(na.pt, nb.pt)
            self._draw_dimension(painter, p0, p1, length_m, seg_id=sid)

        # 5. Indicação de Ângulos entre Paredes nos nós conectados
        self._draw_corner_angles(painter, node_segments)

        # 6. Desenha os nós (pontos de união) com destaque para nó selecionado/arrastado
        for node in self.graph.nodes.values():
            sp = self.world_to_screen(node.x, node.y)
            is_sel = (node.id == self._selected_node_id or node.id == self._drag_node_id)
            if is_sel:
                painter.setPen(QPen(QColor(255, 214, 0), 2.0))
                painter.setBrush(QBrush(QColor(255, 214, 0, 160)))
                painter.drawEllipse(sp, 6.0, 6.0)
            else:
                painter.setPen(QPen(QColor(0, 230, 118), 1.2))
                painter.setBrush(QBrush(QColor(15, 23, 42)))
                painter.drawEllipse(sp, 3.5, 3.5)

    def _draw_rubberband(self, painter: QPainter) -> None:
        if self._start_pt is None:
            return

        p0_w = self._start_pt
        p1_w = self._current_mouse_world
        p0 = self.world_to_screen(p0_w[0], p0_w[1])
        p1 = self.world_to_screen(p1_w[0], p1_w[1])

        dx = p1.x() - p0.x()
        dy = p1.y() - p0.y()
        length_px = math.hypot(dx, dy)
        half_th_px = (self.graph.default_thickness * self._zoom) / 2.0

        if self.mode == "linha":
            if length_px > 1.0:
                ux = dx / length_px
                uy = dy / length_px
                nx = -uy
                ny = ux

                # Duas linhas paralelas de borda em ciano/azul
                pen_guide_border = QPen(QColor(0, 176, 255, 220), 1.4, Qt.SolidLine)
                painter.setPen(pen_guide_border)

                b0_a = QPointF(p0.x() + nx * half_th_px, p0.y() + ny * half_th_px)
                b1_a = QPointF(p1.x() + nx * half_th_px, p1.y() + ny * half_th_px)
                painter.drawLine(b0_a, b1_a)

                b0_b = QPointF(p0.x() - nx * half_th_px, p0.y() - ny * half_th_px)
                b1_b = QPointF(p1.x() - nx * half_th_px, p1.y() - ny * half_th_px)
                painter.drawLine(b0_b, b1_b)

                # Tampa final temporária
                painter.drawLine(b1_a, b1_b)

            # Linha guia central de traço
            painter.setPen(QPen(QColor(0, 176, 255, 180), 1.0, Qt.DashLine))
            painter.drawLine(p0, p1)

            length_m = dist_2d(p0_w, p1_w)
            self._draw_dimension(painter, p0, p1, length_m, is_preview=True)

        elif self.mode == "retangulo":
            x0, y0 = self.world_to_screen(p0_w[0], p0_w[1]).toTuple()
            x1, y1 = self.world_to_screen(p1_w[0], p1_w[1]).toTuple()
            rect = QRectF(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))

            pen_rect = QPen(QColor(0, 176, 255, 200), 1.4, Qt.DashLine)
            painter.setPen(pen_rect)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

            w_m = abs(p1_w[0] - p0_w[0])
            mid_top_a = QPointF(min(x0, x1), min(y0, y1))
            mid_top_b = QPointF(max(x0, x1), min(y0, y1))
            self._draw_dimension(painter, mid_top_a, mid_top_b, w_m, is_preview=True)

    def _draw_corner_angles(self, painter: QPainter, node_segments: Dict[int, List[int]]) -> None:
        """Desenha arco e texto com o ângulo entre paredes nos cantos (ex: 90.0°)."""
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)

        for nid, seg_ids in node_segments.items():
            if len(seg_ids) == 2:
                node = self.nodes_or_graph_get_node(nid)
                if not node:
                    continue

                s1 = self.graph.segments[seg_ids[0]]
                s2 = self.graph.segments[seg_ids[1]]

                other1 = self.graph.nodes[s1.node_b_id if s1.node_a_id == nid else s1.node_a_id]
                other2 = self.graph.nodes[s2.node_b_id if s2.node_a_id == nid else s2.node_a_id]

                # Ângulos em graus das duas paredes saindo do nó (em coordenadas de mundo: +y para cima)
                ang1 = math.degrees(math.atan2(other1.y - node.y, other1.x - node.x))
                ang2 = math.degrees(math.atan2(other2.y - node.y, other2.x - node.x))

                diff = abs(ang1 - ang2) % 360.0
                if diff > 180.0:
                    diff = 360.0 - diff

                # Não desenha se forem paredes retas colineares (180°)
                if 1.0 < diff < 179.0:
                    sp = self.world_to_screen(node.x, node.y)
                    # Vetor médio bissetriz para posicionar o badge do ângulo
                    rad1 = math.radians(ang1)
                    rad2 = math.radians(ang2)
                    v1 = (math.cos(rad1), math.sin(rad1))
                    v2 = (math.cos(rad2), math.sin(rad2))
                    bis_x = v1[0] + v2[0]
                    bis_y = v1[1] + v2[1]
                    blen = math.hypot(bis_x, bis_y)
                    if blen > 1e-4:
                        bis_x /= blen
                        bis_y /= blen
                    else:
                        bis_x, bis_y = -v1[1], v1[0]

                    # Offset em pixels para a cota de ângulo
                    offset_px = 24.0
                    ang_pt = QPointF(sp.x() + bis_x * offset_px, sp.y() - bis_y * offset_px)

                    ang_text = f"{diff:.0f}°" if abs(diff - round(diff)) < 0.1 else f"{diff:.1f}°"
                    fm = painter.fontMetrics()
                    tw = fm.horizontalAdvance(ang_text)
                    th = fm.height()
                    rect_ang = QRectF(ang_pt.x() - tw / 2.0 - 3, ang_pt.y() - th / 2.0 - 2, tw + 6, th + 4)

                    # Desenha arco indicador
                    arc_r = 16.0
                    arc_rect = QRectF(sp.x() - arc_r, sp.y() - arc_r, arc_r * 2, arc_r * 2)
                    painter.setPen(QPen(QColor(0, 230, 118, 160), 1.2, Qt.DotLine))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawArc(arc_rect, int(min(ang1, ang2) * 16), int(diff * 16))

                    # Badge de texto do ângulo
                    painter.setPen(QPen(QColor(0, 230, 118, 180), 1.0))
                    painter.setBrush(QBrush(QColor(18, 24, 32, 220)))
                    painter.drawRoundedRect(rect_ang, 3.0, 3.0)
                    painter.setPen(QColor(0, 230, 118))
                    painter.drawText(rect_ang, Qt.AlignCenter, ang_text)

    def nodes_or_graph_get_node(self, nid: int):
        return self.graph.nodes.get(nid)

    def _draw_dimension(self, painter: QPainter, p0: QPointF, p1: QPointF, length_m: float, is_preview: bool = False, seg_id: Optional[int] = None) -> None:
        if length_m < 0.1:
            return

        mid = (p0 + p1) / 2.0
        text = f"{length_m:.2f} m ({int(round(length_m * 1000))} mm)"

        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()

        badge_rect = QRectF(mid.x() - tw / 2.0 - 5, mid.y() - th / 2.0 - 3, tw + 10, th + 6)
        if seg_id is not None:
            self._dimension_badges[seg_id] = badge_rect

        is_sel = (seg_id is not None and seg_id == self._selected_seg_id)
        if is_sel:
            bg_col = QColor(255, 180, 0, 240)
            text_col = QColor(0, 0, 0)
            pen_border = QPen(QColor(255, 255, 255), 1.2)
        elif is_preview:
            bg_col = QColor(0, 120, 215, 230)
            text_col = QColor(255, 255, 255)
            pen_border = QPen(QColor(255, 255, 255, 120), 1.0)
        else:
            bg_col = QColor(20, 24, 30, 220)
            text_col = QColor(255, 255, 255)
            pen_border = QPen(QColor(255, 255, 255, 120), 1.0)

        painter.setPen(pen_border)
        painter.setBrush(QBrush(bg_col))
        painter.drawRoundedRect(badge_rect, 4.0, 4.0)

        painter.setPen(text_col)
        painter.drawText(badge_rect, Qt.AlignCenter, text)

    def _draw_snap_marker(self, painter: QPainter) -> None:
        if self._snap_info is None:
            return

        pos = self.world_to_screen(self._current_mouse_world[0], self._current_mouse_world[1])
        col = QColor(0, 230, 118) if self._snap_info == "canto" else QColor(255, 214, 0)

        painter.setPen(QPen(col, 2.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(pos, 8.0, 8.0)
        painter.drawEllipse(pos, 3.0, 3.0)


class WallFloorplanDialog(QDialog):
    """Janela de Diálogo para Desenhar Paredes em Planta Baixa 2D com Extrusão 3D Direta."""

    def __init__(self, viewport, existing_group: Optional[Group] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.viewport = viewport
        self.existing_group = existing_group
        self.setWindowTitle("Planta Baixa 2D — Construtor de Paredes (TrazoMob)")
        self.resize(1000, 700)

        # Carrega o grafo 2D de grupo existente na cena se fornecido ou se houver parede selecionada
        loaded_graph = None
        if self.existing_group is not None:
            loaded_graph = WallGraph2D.from_group(self.existing_group)
        elif self.viewport is not None and hasattr(self.viewport, "scene"):
            # Tenta carregar do grupo de parede selecionado na cena
            for g in getattr(self.viewport.scene, "selection", set()):
                if getattr(g, "ext", {}).get("trazomob_wall"):
                    self.existing_group = g
                    loaded_graph = WallGraph2D.from_group(g)
                    break
            # Se não há seleção, procura se existe algum grupo de parede existente na cena
            if loaded_graph is None:
                for g in getattr(self.viewport.scene, "groups", []):
                    if getattr(g, "ext", {}).get("trazomob_wall"):
                        self.existing_group = g
                        loaded_graph = WallGraph2D.from_group(g)
                        break

        if loaded_graph is not None:
            self.graph = loaded_graph
        else:
            self.graph = WallGraph2D(default_thickness=0.15, default_height=2.60)

        self._setup_ui()
        if self.graph.segments:
            self.sp_thickness.setValue(self.graph.default_thickness)
            self.sp_height.setValue(self.graph.default_height)
            self.lbl_status.setText(f"Paredes carregadas: {len(self.graph.segments)}")

    def _setup_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Canvas 2D
        self.canvas = WallFloorplanCanvas(self.graph, parent=self)
        self.canvas.wall_count_changed.connect(self._on_wall_count_changed)

        # 2. Painel Lateral de Controle
        side_panel = QFrame(self)
        side_panel.setFixedWidth(280)
        side_panel.setStyleSheet("""
            QFrame {
                background-color: #1e222b;
                border-left: 1px solid #2e3544;
                color: #e0e0e0;
            }
            QLabel {
                font-weight: bold;
                font-size: 11px;
                color: #9aa4b2;
            }
            QDoubleSpinBox {
                background-color: #13171f;
                border: 1px solid #363f52;
                border-radius: 4px;
                color: #ffffff;
                padding: 4px 8px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #2b3345;
                border: 1px solid #3e4a63;
                border-radius: 5px;
                color: #ffffff;
                padding: 8px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #38435c;
            }
            QPushButton#btn_build {
                background-color: #00b0ff;
                border: 1px solid #40c4ff;
                color: #000000;
                font-size: 13px;
                padding: 10px;
            }
            QPushButton#btn_build:hover {
                background-color: #40c4ff;
            }
        """)

        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(16, 20, 16, 20)
        side_layout.setSpacing(14)

        # Título
        title_lbl = QLabel("📐 Parâmetros da Parede", side_panel)
        title_lbl.setStyleSheet("font-size: 14px; color: #ffffff;")
        side_layout.addWidget(title_lbl)

        # Ferramentas de desenho e seleção
        tool_box = QHBoxLayout()
        self.btn_tool_line = QPushButton("📏 Parede", side_panel)
        self.btn_tool_line.setCheckable(True)
        self.btn_tool_line.setChecked(True)
        self.btn_tool_line.clicked.connect(lambda: self._set_mode("linha"))

        self.btn_tool_rect = QPushButton("🔲 Cômodo", side_panel)
        self.btn_tool_rect.setCheckable(True)
        self.btn_tool_rect.clicked.connect(lambda: self._set_mode("retangulo"))

        self.btn_tool_select = QPushButton("👆 Selecionar", side_panel)
        self.btn_tool_select.setCheckable(True)
        self.btn_tool_select.clicked.connect(lambda: self._set_mode("selecionar"))

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.btn_tool_line)
        self.btn_group.addButton(self.btn_tool_rect)
        self.btn_group.addButton(self.btn_tool_select)

        tool_box.addWidget(self.btn_tool_line)
        tool_box.addWidget(self.btn_tool_rect)
        tool_box.addWidget(self.btn_tool_select)
        side_layout.addLayout(tool_box)

        # Espessura
        side_layout.addWidget(QLabel("Espessura da Parede (m):", side_panel))
        self.sp_thickness = QDoubleSpinBox(side_panel)
        self.sp_thickness.setRange(0.05, 0.50)
        self.sp_thickness.setSingleStep(0.01)
        self.sp_thickness.setValue(0.15)
        self.sp_thickness.valueChanged.connect(self._on_params_changed)
        side_layout.addWidget(self.sp_thickness)

        # Altura / Pé-direito
        side_layout.addWidget(QLabel("Pé-Direito / Altura (m):", side_panel))
        self.sp_height = QDoubleSpinBox(side_panel)
        self.sp_height.setRange(1.00, 6.00)
        self.sp_height.setSingleStep(0.10)
        self.sp_height.setValue(2.60)
        self.sp_height.valueChanged.connect(self._on_params_changed)
        side_layout.addWidget(self.sp_height)

        # Opções automáticas de piso e teto
        self.chk_floor = QCheckBox("Gerar Piso Automaticamente", side_panel)
        self.chk_floor.setChecked(True)
        side_layout.addWidget(self.chk_floor)

        self.chk_ceiling = QCheckBox("Gerar Teto / Forro", side_panel)
        self.chk_ceiling.setChecked(False)
        side_layout.addWidget(self.chk_ceiling)

        # Status / Contador
        self.lbl_status = QLabel("Paredes desenhadas: 0", side_panel)
        self.lbl_status.setStyleSheet("color: #00e676; font-size: 11px;")
        side_layout.addWidget(self.lbl_status)

        # Dicas de uso
        hints = QLabel("💡 <b>Dicas de Operação:</b><br>"
                       "• <b>Duplo clique</b> na medida para corrigir o valor.<br>"
                       "• <b>Selecionar</b>: clique e arraste junções em T ou cantos para reposicionar.<br>"
                       "• <b>Delete</b>: exclui a parede selecionada.<br>"
                       "• <b>Shift</b>: força alinhamento a 90°.<br>"
                       "• <b>Scroll</b>: Zoom / <b>Botão Meio</b>: Pan.<br>"
                       "• <b>Esc / Botão Direito</b>: Cancela.", side_panel)
        hints.setStyleSheet("color: #788599; font-weight: normal; font-size: 11px; line-height: 1.4;")
        hints.setWordWrap(True)
        side_layout.addWidget(hints)

        side_layout.addStretch()

        # Botões de Ação
        btn_undo = QPushButton("↩️ Desfazer (Ctrl+Z)", side_panel)
        btn_undo.clicked.connect(self.canvas.undo)
        side_layout.addWidget(btn_undo)

        btn_clear = QPushButton("🗑️ Limpar Tudo", side_panel)
        btn_clear.clicked.connect(self.canvas.clear_all)
        side_layout.addWidget(btn_clear)

        btn_reset_cam = QPushButton("🔍 Centralizar Visão", side_panel)
        btn_reset_cam.clicked.connect(self.canvas.reset_view)
        side_layout.addWidget(btn_reset_cam)

        self.btn_build = QPushButton("🧱 Concluir e Gerar no 3D", side_panel)
        self.btn_build.setObjectName("btn_build")
        self.btn_build.clicked.connect(self._build_3d_and_close)
        side_layout.addWidget(self.btn_build)

        root_layout.addWidget(self.canvas, 1)
        root_layout.addWidget(side_panel)

    def _set_mode(self, mode: str) -> None:
        self.canvas.mode = mode
        self.canvas._start_pt = None
        self.canvas.update()

    def _on_params_changed(self) -> None:
        self.graph.default_thickness = self.sp_thickness.value()
        self.graph.default_height = self.sp_height.value()
        self.canvas.update()

    def _on_wall_count_changed(self, count: int) -> None:
        self.lbl_status.setText(f"Paredes desenhadas: {count}")

    def _build_3d_and_close(self) -> None:
        if self.graph.is_empty():
            self.reject()
            return

        scene = getattr(self.viewport, "scene", None)
        if scene is not None:
            group_name = self.existing_group.name if self.existing_group else "Ambiente Paredes"
            # Constrói o sólido extrudado contínuo a partir do grafo 2D
            wall_grp = self.graph.build_3d_group(
                scene,
                altura_m=self.sp_height.value(),
                name=group_name,
            )
            if wall_grp is not None:
                if self.existing_group is not None and self.existing_group in scene.groups:
                    idx = scene.groups.index(self.existing_group)
                    scene.groups[idx] = wall_grp
                else:
                    scene.groups.append(wall_grp)

                scene.version += 1
                if hasattr(self.viewport, "flash_status"):
                    self.viewport.flash_status(f"🧱 Paredes atualizadas com sucesso! ({len(self.graph.segments)} segmentos)")
                self.viewport.update()

        self.accept()
