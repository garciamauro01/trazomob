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
from .wall_plan_2d import WallGraph2D, WallNode2D, dist_2d
from .wall_mesh_builder import WallMeshBuilder


class WallFloorplanCanvas(QWidget):
    """Canvas 2D interativo com grid, zoom, pan e cotas dinâmicas em tempo real."""

    wall_count_changed = Signal(int)
    wall_selected = Signal(int, float)  # (seg_id, length_m)
    current_length_changed = Signal(float)  # comprimento em tempo real enquanto desenha

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

        # Guias de alinhamento com outros pontos (cantos / nós)
        self._align_guides: List[Tuple[QPointF, QPointF]] = []

        # Estado de seleção e arrasto
        self._selected_seg_id: Optional[int] = None
        self._selected_node_id: Optional[int] = None
        self._selected_dim_id: Optional[int] = None
        self._drag_dim_id: Optional[int] = None
        self._drag_dim_start_mouse: Optional[Tuple[float, float]] = None
        self._drag_node_id: Optional[int] = None
        self._drag_mid_seg_id: Optional[int] = None
        self._drag_mid_start_mouse: Optional[Tuple[float, float]] = None
        self._drag_start_mouse: Optional[Tuple[float, float]] = None
        self._dimension_badges: Dict[int, Dict[str, Any]] = {}  # {badge_id: {rect, seg_id, dim_id, length_m}}
        self._next_badge_id: int = 1

        # Modo Cota Livre / Pontos Cotados
        self._cota_points: List[Tuple[float, float]] = []

        # Buffer de digitação direta numérica (VCB tipo SketchUp/AutoCAD)
        self._type_buffer: str = ""
        self._t_ref_info: Optional[Dict[str, Any]] = None

        # Imagem de Referência / Decalque de Fundo
        self._ref_image_path: Optional[str] = None
        self._ref_pixmap: Optional[QPixmap] = None
        self._ref_original_pixmap: Optional[QPixmap] = None
        self._ref_pos_world: Tuple[float, float] = (0.0, 0.0)  # Canto inferior esquerdo em coords do mundo
        self._ref_width_m: float = 10.0  # Largura física da imagem no mundo
        self._ref_opacity: float = 0.5   # Opacidade 0.1 a 1.0
        self._ref_visible: bool = True
        self._ref_rotation: int = 0      # Rotação 0, 90, 180, 270

        # Estados de interação da imagem
        self._drag_ref_start: Optional[Tuple[float, float]] = None
        self._drag_ref_initial_pos: Optional[Tuple[float, float]] = None
        self._calib_points: List[Tuple[float, float]] = []

        self.update_cursor()

    def set_reference_image(self, file_path: str, pos_world: Optional[Tuple[float, float]] = None,
                            width_m: Optional[float] = None, opacity: float = 0.5,
                            rotation: int = 0, visible: bool = True) -> bool:
        """Carrega imagem de referência e define escala e posicionamento."""
        pm = QPixmap(file_path)
        if pm.isNull():
            return False
        self._ref_image_path = file_path
        self._ref_original_pixmap = pm
        self._ref_rotation = rotation % 360
        if self._ref_rotation == 0:
            self._ref_pixmap = pm
        else:
            tr = QTransform().rotate(self._ref_rotation)
            self._ref_pixmap = pm.transformed(tr, Qt.SmoothTransformation)

        aspect = self._ref_pixmap.height() / max(1, self._ref_pixmap.width())
        self._ref_width_m = float(width_m) if (width_m is not None and width_m > 0) else 10.0
        height_m = self._ref_width_m * aspect

        if pos_world is not None:
            self._ref_pos_world = (float(pos_world[0]), float(pos_world[1]))
        else:
            # Centraliza a imagem na origem
            self._ref_pos_world = (-self._ref_width_m / 2.0, -height_m / 2.0)

        self._ref_opacity = float(opacity)
        self._ref_visible = bool(visible)
        self.update()
        return True

    def rotate_reference_image(self, degrees: int = 90) -> None:
        """Rotaciona a imagem de referência em múltiplos de 90 graus."""
        if self._ref_original_pixmap is None:
            return
        self._ref_rotation = (self._ref_rotation + degrees) % 360
        if self._ref_rotation == 0:
            self._ref_pixmap = self._ref_original_pixmap
        else:
            tr = QTransform().rotate(self._ref_rotation)
            self._ref_pixmap = self._ref_original_pixmap.transformed(tr, Qt.SmoothTransformation)
        self.update()

    def remove_reference_image(self) -> None:
        """Remove a imagem de referência do canvas."""
        self._ref_image_path = None
        self._ref_pixmap = None
        self._ref_original_pixmap = None
        self._calib_points.clear()
        if self.mode in ("calibrar_ref", "mover_ref"):
            self.mode = "linha"
            self.update_cursor()
        self.update()

    def _prompt_calibrate_scale(self, current_measured_dist: float) -> None:
        """Abre diálogo solicitando a medida real e ajusta a escala da imagem de referência."""
        if self._ref_pixmap is None:
            return

        scale = bare_number_scale()
        u_name = model_unit()
        p = model_precision()

        cur_val_doc = current_measured_dist / scale
        val_doc, ok = QInputDialog.getDouble(
            self,
            "Calibrar Escala da Imagem",
            f"Qual é o comprimento real entre os 2 pontos clicados ({u_name})?:",
            value=round(cur_val_doc, p),
            minValue=0.001,
            maxValue=100000.0,
            decimals=p
        )
        if ok and val_doc > 0:
            target_real_m = val_doc * scale
            ratio = target_real_m / current_measured_dist
            self._ref_width_m *= ratio
            self.update()

    def update_cursor(self, hovering_handle: bool = False) -> None:
        """Atualiza o ponteiro do mouse de acordo com a ferramenta ativa e contexto de hover."""
        if self._pan_start is not None:
            self.setCursor(Qt.ClosedHandCursor)
        elif self.mode == "calibrar_ref":
            self.setCursor(Qt.CrossCursor)
        elif self.mode == "mover_ref":
            self.setCursor(Qt.OpenHandCursor if self._drag_ref_start is None else Qt.ClosedHandCursor)
        elif self.mode in ("linha", "retangulo", "cota"):
            # Modo desenho ou cotagem: cruz de precisão (estilo CAD)
            self.setCursor(Qt.CrossCursor)
        elif self.mode == "selecionar":
            if self._drag_node_id is not None:
                self.setCursor(Qt.SizeAllCursor)
            elif hovering_handle:
                # Pairando sobre um nó arrastável
                self.setCursor(Qt.SizeAllCursor)
            else:
                # Modo seleção: seta padrão
                self.setCursor(Qt.ArrowCursor)
        else:
            self.setCursor(Qt.ArrowCursor)


    def reset_view(self) -> None:
        self._offset_x = self.width() / 2.0
        self._offset_y = self.height() / 2.0
        self._zoom = 80.0
        self.update()

    def zoom_extents(self) -> None:
        """Enquadra a planta inteira ou a imagem de referência no canvas ajustando zoom e deslocamento (pan)."""
        xs = [n.x for n in self.graph.nodes.values()]
        ys = [n.y for n in self.graph.nodes.values()]

        if self._ref_pixmap is not None and self._ref_visible:
            rx, ry = self._ref_pos_world
            rw = self._ref_width_m
            rh = rw * (self._ref_pixmap.height() / max(1, self._ref_pixmap.width()))
            xs.extend([rx, rx + rw])
            ys.extend([ry, ry + rh])

        if not xs:
            self.reset_view()
            return
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        span_x = max(0.5, max_x - min_x)
        span_y = max(0.5, max_y - min_y)

        w = max(200.0, float(self.width()))
        h = max(200.0, float(self.height()))
        margin = 80.0

        scale_x = (w - margin * 2.0) / span_x
        scale_y = (h - margin * 2.0) / span_y
        fit_zoom = max(10.0, min(scale_x, scale_y, 300.0))

        mid_x = (min_x + max_x) / 2.0
        mid_y = (min_y + max_y) / 2.0

        self._zoom = fit_zoom
        self._offset_x = (w / 2.0) - mid_x * self._zoom
        self._offset_y = (h / 2.0) + mid_y * self._zoom
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
        state = {
            "segments": [],
            "dimensions": []
        }
        for seg in self.graph.segments.values():
            na = self.graph.nodes[seg.node_a_id]
            nb = self.graph.nodes[seg.node_b_id]
            state["segments"].append((na.x, na.y, nb.x, nb.y, seg.thickness, seg.height))
        for did, dim in self.graph.dimensions.items():
            state["dimensions"].append({
                "id": did,
                "p1": dim.p1,
                "p2": dim.p2,
                "seg_id": dim.seg_id,
                "offset": dim.offset,
                "node_a_id": dim.node_a_id,
                "node_b_id": dim.node_b_id,
            })
        self._history.append(state)

    def undo(self) -> bool:
        if not self._history:
            if self._start_pt is not None:
                self._start_pt = None
                self.update()
                return True
            return False

        last_state = self._history.pop()
        self.graph.clear()
        if isinstance(last_state, dict):
            for item in last_state.get("segments", []):
                x1, y1, x2, y2, th, h = item
                self.graph.add_segment(x1, y1, x2, y2, thickness=th)
            for d in last_state.get("dimensions", []):
                self.graph.add_dimension(d["p1"], d["p2"], seg_id=d.get("seg_id"), offset=d.get("offset", 0.25))
                # Restore node associations if present (for persisted dimensions)
                dim = self.graph.dimensions.get(d["id"])
                if dim is not None:
                    dim.node_a_id = d.get("node_a_id")
                    dim.node_b_id = d.get("node_b_id")
        else:
            # Compatibilidade com histórico legado simples
            for x1, y1, x2, y2 in last_state:
                self.graph.add_segment(x1, y1, x2, y2)
        self._start_pt = None
        self._selected_dim_id = None
        self._selected_seg_id = None
        self._selected_node_id = None
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
            self.setCursor(Qt.ClosedHandCursor)
            return

        if event.button() == Qt.RightButton:
            if self._start_pt is not None:
                # Se estava no meio do desenho da parede, cancelar traço
                self._start_pt = None
                self._selected_seg_id = None
                self._selected_node_id = None
                self._drag_node_id = None
                self.update()
                return
            else:
                # Se não havia traço ativo, botão direito funciona como Pan fluido
                self._selected_seg_id = None
                self._selected_node_id = None
                self._drag_node_id = None
                self._pan_start = event.position()
                self.setCursor(Qt.ClosedHandCursor)
                self.update()
                return

        if event.button() == Qt.LeftButton:
            wx, wy = self.screen_to_world(event.position().x(), event.position().y())
            click_pos = event.position()

            # Modo Mover Imagem de Referência
            if self.mode == "mover_ref":
                if self._ref_pixmap is not None:
                    self._drag_ref_start = (wx, wy)
                    self._drag_ref_initial_pos = self._ref_pos_world
                    self.setCursor(Qt.ClosedHandCursor)
                    return

            # Modo Cotar: suporte a clique direto na parede ou seleção de 2 pontos livres
            if self.mode == "cota":
                # 1. Checa se o usuário clicou em um PONTO notável (canto de face ou nó do grafo)
                snap_pt, has_point_snap = self._snap_point_or_face(wx, wy)

                if has_point_snap or len(self._cota_points) > 0:
                    # O usuário clicou em um ponto (ou já está no meio da seleção de 2 pontos)
                    if len(self._cota_points) == 0:
                        # Primeiro ponto selecionado: armazena e NÃO abre caixa de diálogo de cotar!
                        # Fica aguardando o clique no segundo ponto.
                        self._cota_points.append(snap_pt)
                        self.update()
                        return
                    elif len(self._cota_points) == 1:
                        # Segundo ponto selecionado: agora sim cria a cota entre p1 e p2 e abre para cotar
                        p1 = self._cota_points[0]
                        p2 = snap_pt
                        self._cota_points.clear()
                        if dist_2d(p1, p2) > 0.01:
                            self._save_history()
                            seg_assoc = self._find_segment_for_dimension(p1, p2)
                            dim_id = self.graph.add_dimension(p1, p2, seg_id=seg_assoc)
                            self._selected_dim_id = dim_id
                            self._selected_seg_id = None
                            self._selected_node_id = None
                            self.update()
                            if dim_id is not None:
                                self._edit_custom_dimension_dialog(dim_id)
                        return

                # 2. Se NÃO clicou em nenhum ponto e ainda não iniciou pontos, checa se clicou diretamente em uma LINHA
                # Prioridade: linha/aresta da face real da parede onde o usuário clicou (interna ou externa)
                polys = self.graph.compute_wall_polygons()
                best_face_edge = None
                best_face_dist = 0.20
                best_face_sid = None

                for sid, quad in polys.items():
                    for i in range(4):
                        p_a = quad[i]
                        p_b = quad[(i + 1) % 4]
                        dx = p_b[0] - p_a[0]
                        dy = p_b[1] - p_a[1]
                        l2 = dx * dx + dy * dy
                        if l2 < 0.04:  # ignora tampas transversais menores que a espessura
                            continue
                        t = max(0.0, min(1.0, ((wx - p_a[0]) * dx + (wy - p_a[1]) * dy) / l2))
                        proj = (p_a[0] + t * dx, p_a[1] + t * dy)
                        d = dist_2d((wx, wy), proj)
                        if d < best_face_dist:
                            best_face_dist = d
                            best_face_edge = (p_a, p_b)
                            best_face_sid = sid

                if best_face_edge is not None and best_face_sid is not None:
                    # Clicou diretamente na linha da face específica (interna ou externa):
                    # Delimita a cota rigorosamente entre os dois pontos daquela linha de face!
                    p1_face, p2_face = best_face_edge
                    self._save_history()
                    dim_id = self.graph.add_dimension(p1_face, p2_face, seg_id=best_face_sid)
                    self._selected_dim_id = dim_id
                    self._selected_seg_id = None
                    self._selected_node_id = None
                    self.update()
                    if dim_id is not None:
                        self._edit_custom_dimension_dialog(dim_id)
                    return

                hit_seg_cota = self.graph.find_segment_at(wx, wy, threshold=0.25)
                if hit_seg_cota is not None and hit_seg_cota in self.graph.segments:
                    # Clicou no eixo central
                    seg = self.graph.segments[hit_seg_cota]
                    na = self.graph.nodes[seg.node_a_id]
                    nb = self.graph.nodes[seg.node_b_id]
                    self._save_history()
                    dim_id = self.graph.add_dimension(na.pt, nb.pt, seg_id=hit_seg_cota)
                    self._selected_dim_id = dim_id
                    self._selected_seg_id = None
                    self._selected_node_id = None
                    self.update()
                    if dim_id is not None:
                        self._edit_custom_dimension_dialog(dim_id)
                    return
                else:
                    # Clicou no vazio: marca o primeiro ponto livre e aguarda o segundo
                    self._cota_points.append((wx, wy))
                    self.update()
                    return

            # 1. PRIORIDADE ABSOLUTA: Checa se clicou na alça de arraste (grip do ponto médio) da parede selecionada
            if self._start_pt is None and self._selected_seg_id is not None and self._selected_seg_id in self.graph.segments:
                seg_cur = self.graph.segments[self._selected_seg_id]
                na_c = self.graph.nodes.get(seg_cur.node_a_id)
                nb_c = self.graph.nodes.get(seg_cur.node_b_id)
                if na_c and nb_c:
                    sp_mid = self.world_to_screen((na_c.x + nb_c.x) / 2.0, (na_c.y + nb_c.y) / 2.0)
                    px_dist = math.hypot(click_pos.x() - sp_mid.x(), click_pos.y() - sp_mid.y())
                    # Tolerância de 15 pixels na tela ou 0.25m no mundo
                    m_wx = (na_c.x + nb_c.x) / 2.0
                    m_wy = (na_c.y + nb_c.y) / 2.0
                    if px_dist <= 15.0 or dist_2d((wx, wy), (m_wx, m_wy)) <= 0.25:
                        self._drag_mid_seg_id = self._selected_seg_id
                        self._drag_mid_start_mouse = (wx, wy)
                        self._save_history()
                        self.setCursor(Qt.SizeAllCursor)
                        self.update()
                        return

            # Se estiver no modo selecionar:
            if self.mode == "selecionar":
                # 1. Checa se clicou em um badge de cota
                for bid, binfo in self._dimension_badges.items():
                    if binfo["rect"].contains(click_pos):
                        if binfo.get("dim_id") is not None:
                            self._selected_dim_id = binfo["dim_id"]
                            self._selected_seg_id = None
                            self._selected_node_id = None
                            self._drag_dim_id = binfo["dim_id"]
                            self._drag_dim_start_mouse = (wx, wy)
                            self._save_history()
                            self.update()
                            return
                        elif binfo.get("seg_id") is not None:
                            self._selected_seg_id = binfo["seg_id"]
                            self._selected_node_id = None
                            self._selected_dim_id = None
                            seg_len = self.graph.segments[binfo["seg_id"]].length(self.graph)
                            self.wall_selected.emit(binfo["seg_id"], seg_len)
                            self.update()
                            return

                # 2. Checa se clicou na linha de alguma cota personalizada
                for did, d_obj in self.graph.dimensions.items():
                    p1_s = self.world_to_screen(d_obj.p1[0], d_obj.p1[1])
                    p2_s = self.world_to_screen(d_obj.p2[0], d_obj.p2[1])
                    dx_s = p2_s.x() - p1_s.x()
                    dy_s = p2_s.y() - p1_s.y()
                    L_s = math.hypot(dx_s, dy_s)
                    if L_s > 1.0:
                        nx_s = -dy_s / L_s
                        ny_s = dx_s / L_s
                        off_px = d_obj.offset * self._zoom
                        c1 = QPointF(p1_s.x() + nx_s * off_px, p1_s.y() + ny_s * off_px)
                        c2 = QPointF(p2_s.x() + nx_s * off_px, p2_s.y() + ny_s * off_px)
                        # Distância do clique ao segmento (c1 -> c2) em pixels
                        line_vec = (c2.x() - c1.x(), c2.y() - c1.y())
                        pt_vec = (click_pos.x() - c1.x(), click_pos.y() - c1.y())
                        t_proj = max(0.0, min(1.0, (pt_vec[0] * line_vec[0] + pt_vec[1] * line_vec[1]) / (L_s * L_s)))
                        proj_px = (c1.x() + t_proj * line_vec[0], c1.y() + t_proj * line_vec[1])
                        d_click = math.hypot(click_pos.x() - proj_px[0], click_pos.y() - proj_px[1])
                        if d_click <= 8.0:
                            self._selected_dim_id = did
                            self._selected_seg_id = None
                            self._selected_node_id = None
                            self._drag_dim_id = did
                            self._drag_dim_start_mouse = (wx, wy)
                            self._save_history()
                            self.update()
                            return

                hit_node = self.graph.find_node_at(wx, wy, threshold=0.25)
                if hit_node is not None:
                    self._selected_node_id = hit_node
                    self._selected_seg_id = None
                    self._selected_dim_id = None
                    self._drag_node_id = hit_node
                    self._drag_start_mouse = (wx, wy)
                    self._save_history()
                    self.update()
                    return

                hit_seg = self.graph.find_segment_at(wx, wy, threshold=0.25)
                if hit_seg is not None:
                    self._selected_seg_id = hit_seg
                    self._selected_node_id = None
                    self._selected_dim_id = None
                    seg_len = self.graph.segments[hit_seg].length(self.graph)
                    self.wall_selected.emit(hit_seg, seg_len)
                    self.update()
                    return

                # Clicou no vazio: desmarca e atualiza os inputs para os padrões globais
                self._selected_node_id = None
                self._selected_seg_id = None
                self._selected_dim_id = None
                self.wall_selected.emit(0, 0.0)
                self.update()
                return

            # Se não estiver no meio de um traço (_start_pt is None), checa seleção no modo linha
            if self._start_pt is None:
                clicked_dim_seg = None
                clicked_dim_id = None
                for bid, binfo in self._dimension_badges.items():
                    if binfo["rect"].contains(click_pos):
                        clicked_dim_seg = binfo.get("seg_id")
                        clicked_dim_id = binfo.get("dim_id")
                        break

                if clicked_dim_id is not None:
                    self._selected_dim_id = clicked_dim_id
                    self._selected_seg_id = None
                    self._selected_node_id = None
                    self._start_pt = None
                    self.update()
                    return

                # No modo 'linha', um clique sobre uma parede existente NÃO deve apenas selecioná-la e bloquear
                # o desenho; ele deve ancorar e iniciar a nova parede (ex: divisória ou cômodo anexo)!
                hit_seg = clicked_dim_seg if clicked_dim_seg is not None else self.graph.find_segment_at(wx, wy, threshold=0.20)
                hit_node = self.graph.find_node_at(wx, wy, threshold=0.20)
                if clicked_dim_seg is not None and hit_seg is not None and hit_node is None:
                    self._selected_seg_id = hit_seg
                    self._selected_node_id = None
                    self._selected_dim_id = None
                    self._start_pt = None
                    seg_len = self.graph.segments[hit_seg].length(self.graph)
                    self.wall_selected.emit(hit_seg, seg_len)
                    self.update()
                    return
                elif hit_node is None and clicked_dim_seg is None:
                    if self._selected_seg_id is not None or self._selected_dim_id is not None:
                        self._selected_seg_id = None
                        self._selected_dim_id = None
                        self.wall_selected.emit(0, 0.0)
                        self.update()

            # Modo de desenho ("linha" ou "retangulo")
            # 1. Aplica alinhamento com outros pontos/nós da cena (guias X e Y)
            wx, wy = self._align_to_existing_points(wx, wy)

            # 2. Aplica snap a cantos ou paredes
            wx, wy, _ = self.graph.snap_point(wx, wy, threshold=0.25)

            # 3. Snap ortogonal a 90 graus se shift ou se próximo do ponto inicial
            if self._start_pt is not None:
                wx, wy = self._ortho_align(self._start_pt, (wx, wy), force_ortho=bool(event.modifiers() & Qt.ShiftModifier))

            if self.mode == "linha":
                if self._start_pt is None:
                    self._start_pt = (wx, wy)
                else:
                    # Ignora clique acidental no mesmo ponto de in?cio (evita cancelar o tra?o da parede)
                    if math.hypot(wx - self._start_pt[0], wy - self._start_pt[1]) < 0.05:
                        return

                    self._save_history()
                    seg_id = self.graph.add_segment(self._start_pt[0], self._start_pt[1], wx, wy)
                    self.graph.merge_close_nodes(threshold=0.25)
                    self.wall_count_changed.emit(len(self.graph.segments))

                    # Verifica se o ponto final conectou a um nó que já tinha paredes (fechando o cômodo/ciclo)
                    # Se fechou um ciclo, encerra a cadeia contínua para não puxar mais segmentos
                    end_node_id = self.graph.find_node_at(wx, wy, threshold=0.25)
                    deg = 0
                    if end_node_id is not None:
                        deg = sum(1 for s in self.graph.segments.values() if s.node_a_id == end_node_id or s.node_b_id == end_node_id)

                    if deg >= 2:
                        # Fechou o cômodo ou conectou a um canto/T existente: encerra o traço contínuo
                        self._start_pt = None
                    else:
                        self._start_pt = (wx, wy)
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
                    self.graph.merge_close_nodes(threshold=0.25)
                    self._start_pt = None
                    self.wall_count_changed.emit(len(self.graph.segments))

            self.update()

    def _align_to_existing_points(self, wx: float, wy: float, tol_px: float = 12.0) -> Tuple[float, float]:
        """Detecta alinhamento horizontal (mesmo Y) e vertical (mesmo X) com nós existentes e cria guias."""
        self._align_guides.clear()
        tol_m = tol_px / max(1.0, self._zoom)

        best_x = wx
        best_y = wy
        min_dx = tol_m
        min_dy = tol_m
        align_node_x = None
        align_node_y = None

        for nid, node in self.graph.nodes.items():
            # Não alinha consigo mesmo se estiver arrastando
            if nid == self._drag_node_id:
                continue

            # Alinhamento vertical (mesmo X)
            dx = abs(node.x - wx)
            if dx <= min_dx:
                min_dx = dx
                best_x = node.x
                align_node_x = node

            # Alinhamento horizontal (mesmo Y)
            dy = abs(node.y - wy)
            if dy <= min_dy:
                min_dy = dy
                best_y = node.y
                align_node_y = node

        # Registra as linhas de guia para desenhar na tela
        if align_node_x is not None:
            p_top = self.world_to_screen(best_x, align_node_x.y)
            p_cur = self.world_to_screen(best_x, best_y)
            self._align_guides.append((p_top, p_cur))

        if align_node_y is not None:
            p_lat = self.world_to_screen(align_node_y.x, best_y)
            p_cur = self.world_to_screen(best_x, best_y)
            self._align_guides.append((p_lat, p_cur))

        return best_x, best_y

    def _snap_point_or_face(self, wx: float, wy: float) -> Tuple[Point2D, bool]:
        """Ancora no ponto notável mais próximo (canto de face ou nó do grafo).
        
        Retorna:
            (ponto_snappado, foi_encontrado_ponto_notavel)
        """
        best_pt = (wx, wy)
        min_dist = 0.22  # tolerância precisa de snap

        # 1. Cantos reais das faces da parede (face interna e face externa)
        polys = self.graph.compute_wall_polygons()
        found = False
        for quad in polys.values():
            for corner in quad:
                d = dist_2d((wx, wy), corner)
                if d < min_dist:
                    min_dist = d
                    best_pt = corner
                    found = True

        # 2. Se não estiver perto de nenhum canto da face, checa os nós centrais do grafo
        for node in self.graph.nodes.values():
            d = dist_2d((wx, wy), (node.x, node.y))
            if d < min_dist:
                min_dist = d
                best_pt = (node.x, node.y)
                found = True

        return best_pt, found

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

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Duplo clique em uma cota ou parede para editar a medida numericamente."""
        click_pos = event.position()
        target_seg_id = None
        target_dim_id = None
        target_len_m = None

        # 1. Checa se clicou no badge de cota
        for bid, binfo in self._dimension_badges.items():
            if binfo["rect"].contains(click_pos):
                target_seg_id = binfo.get("seg_id")
                target_dim_id = binfo.get("dim_id")
                target_len_m = binfo["length_m"]
                break

        if target_dim_id is not None:
            self._edit_custom_dimension_dialog(target_dim_id)
            return

        # 2. Se não clicou no badge, checa se clicou próximo de alguma parede
        if target_seg_id is None:
            wx, wy = self.screen_to_world(click_pos.x(), click_pos.y())
            target_seg_id = self.graph.find_segment_at(wx, wy, threshold=0.30)

        if target_seg_id is not None:
            self._edit_segment_length_dialog(target_seg_id, current_face_len=target_len_m)

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

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pan_start is not None:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self._offset_x += delta.x()
            self._offset_y += delta.y()
            self.update()
            return

        wx, wy = self.screen_to_world(event.position().x(), event.position().y())

        # Arrastar imagem de referência
        if self.mode == "mover_ref" and self._drag_ref_start is not None and self._drag_ref_initial_pos is not None:
            dwx = wx - self._drag_ref_start[0]
            dwy = wy - self._drag_ref_start[1]
            self._ref_pos_world = (self._drag_ref_initial_pos[0] + dwx, self._drag_ref_initial_pos[1] + dwy)
            self.update()
            return

        # No modo calibrar imagem, atualiza tela para desenhar linha elástica
        if self.mode == "calibrar_ref":
            self._current_mouse_world = (wx, wy)
            self.update()
            return

        # Se estiver arrastando a linha de afastamento (offset) de uma cota selecionada:
        if self._drag_dim_id is not None and self._drag_dim_start_mouse is not None:
            dim_cur = self.graph.dimensions.get(self._drag_dim_id)
            if dim_cur:
                dx = dim_cur.p2[0] - dim_cur.p1[0]
                dy = dim_cur.p2[1] - dim_cur.p1[1]
                L = math.hypot(dx, dy)
                if L > 1e-4:
                    # Vetor normal unitário no plano mundo
                    nx = -dy / L
                    ny = dx / L
                    # Projeção do vetor de p1 ao mouse atual sobre a normal
                    proj_offset = (wx - dim_cur.p1[0]) * nx + (wy - dim_cur.p1[1]) * ny
                    dim_cur.offset = proj_offset
                    self.update()
                    return

        # Se estiver arrastando um nó (ex: junção em T ou canto de parede):
        # Se estiver arrastando a al?a m?dia da parede (deslocamento paralelo):
        if self._drag_mid_seg_id is not None and self._drag_mid_start_mouse is not None:
            seg = self.graph.segments.get(self._drag_mid_seg_id)
            if seg:
                na = self.graph.nodes.get(seg.node_a_id)
                nb = self.graph.nodes.get(seg.node_b_id)
                if na and nb:
                    dx = nb.x - na.x
                    dy = nb.y - na.y
                    L = math.hypot(dx, dy)
                    if L > 1e-6:
                        nx, ny = -dy / L, dx / L
                        mdx = wx - self._drag_mid_start_mouse[0]
                        mdy = wy - self._drag_mid_start_mouse[1]
                        proj_dist = mdx * nx + mdy * ny
                        shift_x = nx * proj_dist
                        shift_y = ny * proj_dist
                        self.graph.move_node(seg.node_a_id, na.x + shift_x, na.y + shift_y)
                        self._drag_mid_start_mouse = (wx, wy)
                        self.update()
                        return

        if self._drag_node_id is not None:
            self.update_cursor(hovering_handle=True)
            # Alinha com outros nós
            wx, wy = self._align_to_existing_points(wx, wy)
            # Aplica snap ortogonal ou de grid se shift estiver pressionado
            if bool(event.modifiers() & Qt.ShiftModifier) and self._drag_start_mouse:
                wx, wy = self._ortho_align(self._drag_start_mouse, (wx, wy), force_ortho=True)
            self.graph.move_node(self._drag_node_id, wx, wy)
            self._current_mouse_world = (wx, wy)
            self.update()
            return

        # Verifica se o mouse está pairando sobre a alça de arraste da parede selecionada
        hover_grip = False
        if self._selected_seg_id is not None and self._selected_seg_id in self.graph.segments:
            seg_h = self.graph.segments[self._selected_seg_id]
            na_h = self.graph.nodes.get(seg_h.node_a_id)
            nb_h = self.graph.nodes.get(seg_h.node_b_id)
            if na_h and nb_h:
                sp_mid = self.world_to_screen((na_h.x + nb_h.x) / 2.0, (na_h.y + nb_h.y) / 2.0)
                if math.hypot(event.position().x() - sp_mid.x(), event.position().y() - sp_mid.y()) <= 15.0:
                    hover_grip = True

        if hover_grip:
            self.setCursor(Qt.SizeAllCursor)
        elif self.mode == "selecionar":
            hover_nid = self.graph.find_node_at(wx, wy, threshold=0.25)
            self.update_cursor(hovering_handle=(hover_nid is not None))
        else:
            self.update_cursor()

        if self.mode == "cota":
            # No modo cota, destaca os cantos das faces da parede e não força o centro
            self._snap_info = None
            snap_cota, has_snap = self._snap_point_or_face(wx, wy)
            if has_snap and dist_2d((wx, wy), snap_cota) < 0.20:
                wx, wy = snap_cota
                self._snap_info = "canto"
        else:
            # 1. Alinha com outros pontos existentes (guias inteligentes tipo CAD)
            wx, wy = self._align_to_existing_points(wx, wy)

            # 2. Snap magnético para canto ou parede
            wx, wy, snap_type = self.graph.snap_point(wx, wy, threshold=0.25)
            self._snap_info = snap_type

        # Se estiver preparando o primeiro ponto da parede e passar o mouse sobre uma parede existente
        if self._start_pt is None and self.mode == "linha" and snap_type == "parede":
            seg_id = self.graph.find_segment_at(wx, wy, threshold=0.30)
            if seg_id is not None:
                seg = self.graph.segments[seg_id]
                na = self.graph.nodes[seg.node_a_id]
                nb = self.graph.nodes[seg.node_b_id]
                proj, t = self.graph._project_point_on_segment((wx, wy), na.pt, nb.pt)
                d_a = dist_2d(na.pt, proj)
                d_b = dist_2d(nb.pt, proj)
                ref_node = na if d_a <= d_b else nb
                other_node = nb if d_a <= d_b else na
                dist_val = d_a if d_a <= d_b else d_b

                dx = other_node.x - ref_node.x
                dy = other_node.y - ref_node.y
                L = math.hypot(dx, dy)
                u_dir = (dx / L, dy / L) if L > 1e-6 else (1.0, 0.0)

                self._t_ref_info = {
                    "seg_id": seg_id,
                    "ref_node_id": ref_node.id,
                    "ref_pt": ref_node.pt,
                    "other_pt": other_node.pt,
                    "proj_pt": proj,
                    "u_dir": u_dir,
                    "distance_m": dist_val,
                }
                if not self._type_buffer:
                    self.current_length_changed.emit(dist_val)
            else:
                self._t_ref_info = None
        elif self._start_pt is None:
            self._t_ref_info = None

        # 3. Snap ortogonal
        if self._start_pt is not None:
            wx, wy = self._ortho_align(self._start_pt, (wx, wy), force_ortho=bool(event.modifiers() & Qt.ShiftModifier))
            cur_len = dist_2d(self._start_pt, (wx, wy))
            dx = wx - self._start_pt[0]
            dy = wy - self._start_pt[1]
            if cur_len > 1e-4:
                ux, uy = dx / cur_len, dy / cur_len
                ext = self.graph.get_start_extension(self._start_pt, (ux, uy))
                visible_len = max(0.01, cur_len - ext)
            else:
                visible_len = cur_len
            self.current_length_changed.emit(visible_len)

        self._current_mouse_world = (wx, wy)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.MiddleButton, Qt.RightButton) or (event.button() == Qt.LeftButton and self._pan_start is not None):
            self._pan_start = None
            self.update_cursor()

        if event.button() == Qt.LeftButton and self._drag_dim_id is not None:
            self._drag_dim_id = None
            self._drag_dim_start_mouse = None
            self.update_cursor()
            self.update()

        if event.button() == Qt.LeftButton and self._drag_mid_seg_id is not None:
            self._drag_mid_seg_id = None
            self._drag_mid_start_mouse = None
            self.update_cursor()
            self.update()

        if event.button() == Qt.LeftButton and self._drag_ref_start is not None:
            self._drag_ref_start = None
            self._drag_ref_initial_pos = None
            self.update_cursor()
            self.update()

        if event.button() == Qt.LeftButton and self._drag_node_id is not None:
            self.graph.merge_close_nodes(threshold=0.25)
            self._drag_node_id = None
            self._drag_start_mouse = None
            self.wall_count_changed.emit(len(self.graph.segments))
            self.update_cursor()
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
        key = event.key()
        text = event.text()

        if key == Qt.Key_Escape:
            # 1. Se estiver calibrando ou movendo imagem de referência, volta para o modo linha
            if self.mode in ("calibrar_ref", "mover_ref"):
                self.mode = "linha"
                self._calib_points.clear()
                self.update_cursor()
                self.update()
                return

            # 2. Se estiver traçando parede (_start_pt ativo), cancela apenas o traço atual
            if self._start_pt is not None:
                self._start_pt = None
                self._type_buffer = ""
                self.update()
                return

            # 3. Se houver elemento selecionado ou buffer de digitação, limpa a seleção
            if self._selected_seg_id is not None or self._selected_node_id is not None or self._selected_dim_id is not None or self._type_buffer:
                self._selected_node_id = None
                self._selected_seg_id = None
                self._selected_dim_id = None
                self._drag_node_id = None
                self._type_buffer = ""
                self.update()
                return

            # 4. Se não havia nenhuma operação ativa no canvas, passa o evento para o diálogo (que tratará com confirmação)
            super().keyPressEvent(event)
            return
        elif key in (Qt.Key_Delete, Qt.Key_Backspace) and self._selected_dim_id is not None:
            # Exclui cota personalizada selecionada
            self._save_history()
            self.graph.remove_dimension(self._selected_dim_id)
            self._selected_dim_id = None
            self.update()
            return
        elif key in (Qt.Key_Delete, Qt.Key_Backspace) and self._selected_seg_id is not None:
            # Exclui segmento selecionado
            self._save_history()
            del self.graph.segments[self._selected_seg_id]
            self._selected_seg_id = None
            self.wall_count_changed.emit(len(self.graph.segments))
            self.update()
            return
        elif key == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            self.undo()
            return

        # Digitação direta de medidas tipo CAD/SketchUp
        # Se estiver desenhando (iniciou parede com _start_pt) ou tiver uma parede selecionada:
        if (self._start_pt is not None or self._selected_seg_id is not None or self._t_ref_info is not None):
            if text and text in "0123456789.,":
                # Converte vírgula para ponto se necessário
                char = "." if text == "," else text
                if char == "." and "." in self._type_buffer:
                    return
                self._type_buffer += char
                try:
                    val_doc = float(self._type_buffer)
                    scale = bare_number_scale()
                    val_m = val_doc * scale
                    self.current_length_changed.emit(val_m)
                except ValueError:
                    pass
                self.update()
                return
            elif key == Qt.Key_Backspace:
                if self._type_buffer:
                    self._type_buffer = self._type_buffer[:-1]
                    try:
                        val_doc = float(self._type_buffer) if self._type_buffer else 0.0
                        scale = bare_number_scale()
                        self.current_length_changed.emit(val_doc * scale)
                    except ValueError:
                        pass
                    self.update()
                    return
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                if self._type_buffer:
                    try:
                        val_doc = float(self._type_buffer)
                        scale = bare_number_scale()
                        val_m = val_doc * scale
                        self._apply_typed_length(val_m)
                    except ValueError:
                        pass
                    self._type_buffer = ""
                    self.update()
                    return

        super().keyPressEvent(event)

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

        # 0. Imagem de Referência / Decalque de Fundo
        self._draw_reference_image(painter)

        # 1. Desenha Grid Métrico
        self._draw_grid(painter)

        # 2. Desenha Paredes Existentes
        self._draw_walls(painter)

        # 3. Desenha Prévia do que está sendo desenhado (Borracha elástica / Rubberband)
        self._draw_rubberband(painter)

        # 4. Linhas de alinhamento inteligente com outros pontos (traço laranja/ouro)
        self._draw_alignment_guides(painter)

        # 5. Indicador de Snap
        self._draw_snap_marker(painter)
        self._draw_t_junction_tracking(painter)

    def _draw_reference_image(self, painter: QPainter) -> None:
        """Renderiza a imagem de referência de fundo com opacidade ajustável e escala correta."""
        if self._ref_pixmap is None or not self._ref_visible:
            return

        rx, ry = self._ref_pos_world
        rw = self._ref_width_m
        rh = rw * (self._ref_pixmap.height() / max(1, self._ref_pixmap.width()))

        p_top_left = self.world_to_screen(rx, ry + rh)
        p_bottom_right = self.world_to_screen(rx + rw, ry)
        target_rect = QRectF(p_top_left, p_bottom_right)

        painter.save()
        painter.setOpacity(self._ref_opacity)
        painter.drawPixmap(target_rect.toRect(), self._ref_pixmap)

        # Se estiver no modo de mover imagem, desenha borda azul indicativa
        if self.mode == "mover_ref":
            painter.setOpacity(1.0)
            painter.setPen(QPen(QColor(0, 176, 255, 200), 2.0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(target_rect)
        painter.restore()

        # Se estiver no modo calibrar e tiver pontos marcados:
        if self.mode == "calibrar_ref" and self._calib_points:
            painter.save()
            p1_scr = self.world_to_screen(self._calib_points[0][0], self._calib_points[0][1])
            p_cur_scr = self.world_to_screen(self._current_mouse_world[0], self._current_mouse_world[1])

            painter.setPen(QPen(QColor(255, 214, 0), 2.0, Qt.DashLine))
            painter.drawLine(p1_scr, p_cur_scr)

            painter.setPen(QPen(QColor(255, 255, 255), 1.5))
            painter.setBrush(QBrush(QColor(255, 214, 0)))
            painter.drawEllipse(p1_scr, 5.0, 5.0)
            painter.drawEllipse(p_cur_scr, 4.0, 4.0)

            # Cota em tempo real da calibração
            dist_val = dist_2d(self._calib_points[0], self._current_mouse_world)
            lbl_txt = f"Calibrar: {format_length(dist_val)}"
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.setPen(QColor(255, 214, 0))
            mid_p = (p1_scr + p_cur_scr) / 2.0
            painter.drawText(QPointF(mid_p.x() + 10, mid_p.y() - 10), lbl_txt)
            painter.restore()

    def _draw_alignment_guides(self, painter: QPainter) -> None:
        """Desenha linhas tracejadas infinitas/guias indicando alinhamento X ou Y com nós existentes."""
        if not self._align_guides:
            return

        pen_align = QPen(QColor(255, 140, 0, 200), 1.2, Qt.DashLine)
        painter.setPen(pen_align)

        w = self.width()
        h = self.height()

        for p_from, p_to in self._align_guides:
            # Se alinhado verticalmente (mesmo X no screen)
            if abs(p_from.x() - p_to.x()) < 1.0:
                painter.drawLine(QPointF(p_to.x(), 0), QPointF(p_to.x(), h))
            # Se alinhado horizontalmente (mesmo Y no screen)
            elif abs(p_from.y() - p_to.y()) < 1.0:
                painter.drawLine(QPointF(0, p_to.y()), QPointF(w, p_to.y()))
            else:
                painter.drawLine(p_from, p_to)

            # Marcador em cruz no ponto de referência com o qual está alinhando
            painter.drawLine(QPointF(p_from.x() - 4, p_from.y()), QPointF(p_from.x() + 4, p_from.y()))
            painter.drawLine(QPointF(p_from.x(), p_from.y() - 4), QPointF(p_from.x(), p_from.y() + 4))

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

        # 4. Linhas de cota automáticas das paredes no eixo central
        for sid, seg in self.graph.segments.items():
            na = self.graph.nodes[seg.node_a_id]
            nb = self.graph.nodes[seg.node_b_id]
            len_center = dist_2d(na.pt, nb.pt)
            p0 = self.world_to_screen(na.x, na.y)
            p1 = self.world_to_screen(nb.x, nb.y)

            pen_measure = QPen(QColor(70, 140, 245, 180), 1.2, Qt.DashLine)
            painter.setPen(pen_measure)
            painter.drawLine(p0, p1)

            # Cota de comprimento do eixo com registro para duplo clique
            self._draw_dimension(painter, p0, p1, len_center, seg_id=sid)

        # 4.5 Desenha Cotas Personalizadas adicionadas pelo usuário (entre quaisquer dois pontos)
        self._draw_custom_dimensions(painter)

        # 5. Indicação de Ângulos entre Paredes nos nós conectados
        self._draw_corner_angles(painter, node_segments)

        # 6. Desenha os nós (pontos de união) com destaque para nó selecionado/arrastado
        # 5.5 Desenha o grip de arraste paralelo no ponto m?dio da parede selecionada
        if self._selected_seg_id is not None and self._selected_seg_id in self.graph.segments:
            seg_sel = self.graph.segments[self._selected_seg_id]
            na_sel = self.graph.nodes.get(seg_sel.node_a_id)
            nb_sel = self.graph.nodes.get(seg_sel.node_b_id)
            if na_sel and nb_sel:
                mid_wx = (na_sel.x + nb_sel.x) / 2.0
                mid_wy = (na_sel.y + nb_sel.y) / 2.0
                sp_mid = self.world_to_screen(mid_wx, mid_wy)
                painter.setPen(QPen(QColor(255, 255, 255), 1.5))
                painter.setBrush(QBrush(QColor(0, 176, 255, 240) if self._drag_mid_seg_id is None else QColor(255, 214, 0, 240)))
                sz_g = 7.0
                painter.drawRect(QRectF(sp_mid.x() - sz_g / 2.0, sp_mid.y() - sz_g / 2.0, sz_g, sz_g))

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

    def _draw_custom_dimensions(self, painter: QPainter) -> None:
        """Desenha todas as cotas personalizadas inseridas pelo usuário na planta."""
        for did, dim in self.graph.dimensions.items():
            p1_scr = self.world_to_screen(dim.p1[0], dim.p1[1])
            p2_scr = self.world_to_screen(dim.p2[0], dim.p2[1])

            dx = p2_scr.x() - p1_scr.x()
            dy = p2_scr.y() - p1_scr.y()
            L_px = math.hypot(dx, dy)
            if L_px < 1.0:
                continue

            # Vetor normal para afastar a linha de cota dos pontos
            nx = -dy / L_px
            ny = dx / L_px
            off_px = dim.offset * self._zoom

            # Pontos deslocados da linha de cota
            c1 = QPointF(p1_scr.x() + nx * off_px, p1_scr.y() + ny * off_px)
            c2 = QPointF(p2_scr.x() + nx * off_px, p2_scr.y() + ny * off_px)

            # Linhas de extensão / testemunha (dos pontos até a linha de cota)
            is_dim_sel = (did == self._selected_dim_id)
            pen_witness = QPen(QColor(255, 214, 0, 180) if is_dim_sel else QColor(0, 230, 118, 140), 1.0, Qt.DotLine)
            painter.setPen(pen_witness)
            painter.drawLine(p1_scr, c1)
            painter.drawLine(p2_scr, c2)

            # Linha principal da cota
            pen_dim_line = QPen(QColor(255, 214, 0, 255) if is_dim_sel else QColor(0, 230, 118, 220), 1.8 if is_dim_sel else 1.4, Qt.SolidLine)
            painter.setPen(pen_dim_line)
            painter.drawLine(c1, c2)

            # Tiques/barras inclinadas a 45 graus nas extremidades da cota (padrão arquitetônico)
            tick_sz = 5.0
            painter.drawLine(QPointF(c1.x() - tick_sz, c1.y() + tick_sz), QPointF(c1.x() + tick_sz, c1.y() - tick_sz))
            painter.drawLine(QPointF(c2.x() - tick_sz, c2.y() + tick_sz), QPointF(c2.x() + tick_sz, c2.y() - tick_sz))

            # Badge interativo com o valor da cota
            dist_m = dist_2d(dim.p1, dim.p2)
            self._draw_dimension(painter, c1, c2, dist_m, dim_id=did)

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
        th_px = self.graph.default_thickness * self._zoom

        off_l_px = th_px / 2.0
        off_r_px = th_px / 2.0

        if self.mode == "linha":
            if length_px > 1.0:
                # No screen do Qt, Y cresce para baixo enquanto no mundo Y cresce para cima.
                # Vetor u_screen = (dx/length, dy/length).
                # Normal à esquerda no screen que corresponde à normal à esquerda no mundo:
                # No mundo: u = (wdx, wdy), n = (-wdy, wdx).
                # Como sy = offset_y - wy*zoom, dy_screen = -dwy * zoom.
                # Portanto, nx_screen = dy_screen / length_px, ny_screen = -dx_screen / length_px.
                wdx = p1_w[0] - p0_w[0]
                wdy = p1_w[1] - p0_w[1]
                wlen = math.hypot(wdx, wdy)
                if wlen > 1e-6:
                    wnx = -wdy / wlen
                    wny = wdx / wlen
                    # Converte vetor normal do mundo para pixels de tela
                    nx_px = wnx * self._zoom
                    ny_px = -wny * self._zoom

                    # Duas linhas paralelas de borda em ciano/azul
                    pen_guide_border = QPen(QColor(0, 176, 255, 220), 1.4, Qt.SolidLine)
                    painter.setPen(pen_guide_border)

                    factor_l = off_l_px / max(1e-6, th_px)
                    factor_r = off_r_px / max(1e-6, th_px)

                    # Borda esquerda: ponto + n * off_l
                    b0_a = QPointF(p0.x() + nx_px * (self.graph.default_thickness * factor_l),
                                   p0.y() + ny_px * (self.graph.default_thickness * factor_l))
                    b1_a = QPointF(p1.x() + nx_px * (self.graph.default_thickness * factor_l),
                                   p1.y() + ny_px * (self.graph.default_thickness * factor_l))
                    painter.drawLine(b0_a, b1_a)

                    # Borda direita: ponto - n * off_r
                    b0_b = QPointF(p0.x() - nx_px * (self.graph.default_thickness * factor_r),
                                   p0.y() - ny_px * (self.graph.default_thickness * factor_r))
                    b1_b = QPointF(p1.x() - nx_px * (self.graph.default_thickness * factor_r),
                                   p1.y() - ny_px * (self.graph.default_thickness * factor_r))
                    painter.drawLine(b0_b, b1_b)

                    # Tampa final temporária
                    painter.drawLine(b1_a, b1_b)

            # Linha guia de traço / cota
            painter.setPen(QPen(QColor(0, 176, 255, 180), 1.0, Qt.DashLine))
            painter.drawLine(p0, p1)

            total_len_m = dist_2d(p0_w, p1_w)
            if total_len_m > 1e-4:
                dir_u = ((p1_w[0] - p0_w[0]) / total_len_m, (p1_w[1] - p0_w[1]) / total_len_m)
                ext = self.graph.get_start_extension(p0_w, dir_u)
                display_len = max(0.01, total_len_m - ext)
            else:
                display_len = total_len_m
            self._draw_dimension(painter, p0, p1, display_len, is_preview=True)

        elif self.mode == "cota" and self._cota_points:
            p1_scr = self.world_to_screen(self._cota_points[0][0], self._cota_points[0][1])
            p_cur_scr = self.world_to_screen(p1_w[0], p1_w[1])
            pen_cota_prev = QPen(QColor(0, 230, 118, 200), 1.4, Qt.DashLine)
            painter.setPen(pen_cota_prev)
            painter.drawLine(p1_scr, p_cur_scr)
            dist_cota_m = dist_2d(self._cota_points[0], p1_w)
            self._draw_dimension(painter, p1_scr, p_cur_scr, dist_cota_m, is_preview=True)

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

    def _draw_dimension(self, painter: QPainter, p0: QPointF, p1: QPointF, length_m: float, is_preview: bool = False, seg_id: Optional[int] = None, dim_id: Optional[int] = None, face_type: str = "centro") -> None:
        if length_m < 0.001:
            return

        mid = (p0 + p1) / 2.0
        # Se houver digitação direta em andamento, exibe o que está sendo digitado com a unidade
        doc_u = model_unit()
        doc_p = model_precision()
        if is_preview and self._type_buffer:
            text = f"⌨️ {self._type_buffer} {doc_u} (Enter ↵)"
        else:
            text = format_length(length_m, doc_u, doc_p)

        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()

        badge_rect = QRectF(mid.x() - tw / 2.0 - 5, mid.y() - th / 2.0 - 3, tw + 10, th + 6)
        if seg_id is not None or dim_id is not None:
            # Use dim_id (persistent dimension ID) as the badge key
            # instead of _next_badge_id (transient, resets on session reload)
            # This ensures badges persist correctly across session reloads
            badge_key = f"dim_{dim_id}" if dim_id is not None else f"seg_{seg_id}"
            self._dimension_badges[badge_key] = {
                "rect": badge_rect,
                "seg_id": seg_id,
                "dim_id": dim_id,
                "face_type": face_type,
                "length_m": length_m,
            }

        is_sel = (seg_id is not None and seg_id == self._selected_seg_id) or (dim_id is not None and dim_id == self._selected_dim_id)
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



    def _draw_t_junction_tracking(self, painter: QPainter) -> None:
        """Desenha a linha de cota din?mica e ?ncora visual ao rastrear dist?ncia para parede em T."""
        if self._t_ref_info is None or self._start_pt is not None:
            return

        ref_pt = self._t_ref_info["ref_pt"]
        proj_pt = self._t_ref_info["proj_pt"]
        dist_m = self._t_ref_info["distance_m"]

        p_ref = self.world_to_screen(ref_pt[0], ref_pt[1])
        p_proj = self.world_to_screen(proj_pt[0], proj_pt[1])

        # Linha guia de medi??o em ciano brilhante sobre a parede existente
        pen_track = QPen(QColor(0, 230, 255, 230), 2.0, Qt.SolidLine)
        painter.setPen(pen_track)
        painter.drawLine(p_ref, p_proj)

        # Marcador de ?ncora (diamante / rombo) no canto de refer?ncia
        r_sz = 6.0
        poly_anchor = QPolygonF([
            QPointF(p_ref.x(), p_ref.y() - r_sz),
            QPointF(p_ref.x() + r_sz, p_ref.y()),
            QPointF(p_ref.x(), p_ref.y() + r_sz),
            QPointF(p_ref.x() - r_sz, p_ref.y()),
        ])
        painter.setBrush(QBrush(QColor(0, 230, 255, 200)))
        painter.drawPolygon(poly_anchor)

        # Marcador circular no ponto projetado da parede
        painter.setBrush(QBrush(QColor(255, 214, 0, 220)))
        painter.setPen(QPen(QColor(255, 255, 255), 1.2))
        painter.drawEllipse(p_proj, 4.5, 4.5)

        # Cota din?mica com texto
        self._draw_dimension(painter, p_ref, p_proj, dist_m, is_preview=True)
