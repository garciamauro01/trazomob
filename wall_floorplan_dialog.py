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

        # Ferramenta ativa: "linha" (desenhar paredes contínuas) ou "retangulo" (cômodo)
        self.mode = "linha"

        # Estado de desenho
        self._start_pt: Optional[Tuple[float, float]] = None
        self._current_mouse_world: Tuple[float, float] = (0.0, 0.0)
        self._snap_info: Optional[str] = None
        self._history: List[List[Tuple[float, float, float, float]]] = []

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
            # Cancela desenho atual
            if self._start_pt is not None:
                self._start_pt = None
                self.update()
            return

        if event.button() == Qt.LeftButton:
            wx, wy = self.screen_to_world(event.position().x(), event.position().y())
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

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pan_start is not None:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self._offset_x += delta.x()
            self._offset_y += delta.y()
            self.update()
            return

        wx, wy = self.screen_to_world(event.position().x(), event.position().y())
        wx, wy, snap_type = self.graph.snap_point(wx, wy, threshold=0.25)
        self._snap_info = snap_type

        if self._start_pt is not None:
            wx, wy = self._ortho_align(self._start_pt, (wx, wy), force_ortho=bool(event.modifiers() & Qt.ShiftModifier))

        self._current_mouse_world = (wx, wy)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self._pan_start is not None):
            self._pan_start = None

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
        for seg in self.graph.segments.values():
            na = self.graph.nodes[seg.node_a_id]
            nb = self.graph.nodes[seg.node_b_id]

            p0 = self.world_to_screen(na.x, na.y)
            p1 = self.world_to_screen(nb.x, nb.y)

            # Corpo da parede com espessura real em pixels
            th_px = max(4.0, seg.thickness * self._zoom)
            pen_wall = QPen(QColor(200, 210, 225), th_px, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin)
            painter.setPen(pen_wall)
            painter.drawLine(p0, p1)

            # Eixo central da parede (linha fina de guia)
            painter.setPen(QPen(QColor(60, 130, 240, 180), 1.0, Qt.DashLine))
            painter.drawLine(p0, p1)

            # Cota de comprimento
            length_m = dist_2d(na.pt, nb.pt)
            self._draw_dimension(painter, p0, p1, length_m)

        # Desenha os nós (pontos de união)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 230, 118)))
        for node in self.graph.nodes.values():
            sp = self.world_to_screen(node.x, node.y)
            painter.drawEllipse(sp, 4.0, 4.0)

    def _draw_rubberband(self, painter: QPainter) -> None:
        if self._start_pt is None:
            return

        p0_w = self._start_pt
        p1_w = self._current_mouse_world
        p0 = self.world_to_screen(p0_w[0], p0_w[1])
        p1 = self.world_to_screen(p1_w[0], p1_w[1])

        th_px = max(4.0, self.graph.default_thickness * self._zoom)

        if self.mode == "linha":
            # Linha prévia
            pen_preview = QPen(QColor(0, 176, 255, 180), th_px, Qt.SolidLine, Qt.SquareCap)
            painter.setPen(pen_preview)
            painter.drawLine(p0, p1)

            length_m = dist_2d(p0_w, p1_w)
            self._draw_dimension(painter, p0, p1, length_m, is_preview=True)

        elif self.mode == "retangulo":
            x0, y0 = self.world_to_screen(p0_w[0], p0_w[1]).toTuple()
            x1, y1 = self.world_to_screen(p1_w[0], p1_w[1]).toTuple()
            rect = QRectF(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))

            pen_rect = QPen(QColor(0, 176, 255, 180), th_px, Qt.SolidLine, Qt.SquareCap)
            painter.setPen(pen_rect)
            painter.setBrush(QBrush(QColor(0, 176, 255, 30)))
            painter.drawRect(rect)

            w_m = abs(p1_w[0] - p0_w[0])
            h_m = abs(p1_w[1] - p0_w[1])
            mid_top_a = QPointF(min(x0, x1), min(y0, y1))
            mid_top_b = QPointF(max(x0, x1), min(y0, y1))
            self._draw_dimension(painter, mid_top_a, mid_top_b, w_m, is_preview=True)

    def _draw_dimension(self, painter: QPainter, p0: QPointF, p1: QPointF, length_m: float, is_preview: bool = False) -> None:
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
        bg_col = QColor(0, 120, 215, 230) if is_preview else QColor(20, 24, 30, 220)
        painter.setPen(QPen(QColor(255, 255, 255, 120), 1.0))
        painter.setBrush(QBrush(bg_col))
        painter.drawRoundedRect(badge_rect, 4.0, 4.0)

        painter.setPen(QColor(255, 255, 255))
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

        # Ferramentas de desenho
        tool_box = QHBoxLayout()
        self.btn_tool_line = QPushButton("📏 Linha Contínua", side_panel)
        self.btn_tool_line.setCheckable(True)
        self.btn_tool_line.setChecked(True)
        self.btn_tool_line.clicked.connect(lambda: self._set_mode("linha"))

        self.btn_tool_rect = QPushButton("🔲 Retângulo Cômodo", side_panel)
        self.btn_tool_rect.setCheckable(True)
        self.btn_tool_rect.clicked.connect(lambda: self._set_mode("retangulo"))

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.btn_tool_line)
        self.btn_group.addButton(self.btn_tool_rect)

        tool_box.addWidget(self.btn_tool_line)
        tool_box.addWidget(self.btn_tool_rect)
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
                       "• <b>Clique</b> para iniciar e traçar paredes.<br>"
                       "• <b>Shift</b>: força alinhamento a 90°.<br>"
                       "• <b>Scroll</b>: Zoom / <b>Botão Meio</b>: Pan.<br>"
                       "• <b>Esc / Botão Direito</b>: Cancela traço.", side_panel)
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
