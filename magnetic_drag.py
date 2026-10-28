# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Manipulador de Aderência Magnética, Movimentação por Arraste e Cotas Inteligentes para Módulos.

Instala um eventFilter no Viewport (100% contido no plugin) para:
1. Detectar clique e arraste com o botão esquerdo sobre um módulo de marcenaria;
2. Desativar a seleção retangular (box-select) apenas durante o arraste de módulos;
3. Proporcionar Aderência Magnética Inteligente (Snap Magnético):
   - Ao Piso (Z = 0): A base do móvel se fixa magneticamente no chão.
   - Às Paredes: Quando o móvel se aproxima de uma parede contínua,
     a face traseira se alinha e encosta perfeitamente na face interna da parede com 0.0mm de folga.
   - Elevação na Parede: Ao erguer o cursor sobre a parede, o módulo rompe a atração do piso
     e desliza verticalmente fixado na parede (ideal para armários aéreos e nichos).
4. Cotas Dinâmicas de Snap em Tempo Real:
   - Mede as distâncias para todos os lados (4 direções principais + piso/teto) até as paredes
     ou objetos mais próximos.
   - Renderiza linhas de cota com setas e etiquetas com fundo escuro e valores em mm.
   - Mantém as cotas visíveis na tela enquanto o módulo estiver selecionado.
5. Fornecer preview suave em tempo real e registrar o comando reversível (Undo/Redo) no final.
"""
from __future__ import annotations

import math
from typing import Optional, List, Tuple

from PySide6.QtCore import QObject, QEvent, Qt, QPointF, QRectF
from PySide6.QtGui import QVector3D, QMouseEvent, QPainter, QPen, QColor, QFont

from core.group import Group, iter_placements
from core.history import MoveGroupCommand, CompoundCommand


def get_module_bounds(mod: Group) -> Optional[Tuple[float, float, float, float, float, float]]:
    """Calcula os limites AABB do módulo em coordenadas globais (min_x, max_x, min_y, max_y, min_z, max_z)."""
    min_x, max_x = float("inf"), float("-inf")
    min_y, max_y = float("inf"), float("-inf")
    min_z, max_z = float("inf"), float("-inf")
    found = False

    for pg, xf in iter_placements(mod):
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

    if not found:
        return None
    return (min_x, max_x, min_y, max_y, min_z, max_z)


def get_bounds_min_projection(bounds: Tuple[float, float, float, float, float, float], direction: QVector3D) -> float:
    """Calcula a projeção mínima da AABB do móvel ao longo de 'direction' de forma instantânea."""
    min_x, max_x, min_y, max_y, _, _ = bounds
    corners = (
        (min_x, min_y),
        (max_x, min_y),
        (min_x, max_y),
        (max_x, max_y),
    )
    dx, dy = direction.x(), direction.y()
    return min(x * dx + y * dy for x, y in corners)


def draw_snap_dimension_segment(
    viewport,
    painter: QPainter,
    p0: QVector3D,
    p1: QVector3D,
    cota_color: QColor = QColor(0, 140, 255),
    offset_px: float = 0.0,
) -> None:
    """Renderiza uma cota interativa completa com setas e etiqueta de milímetros entre dois pontos 3D."""
    dist_m = (p1 - p0).length()
    if math.isnan(dist_m) or math.isinf(dist_m) or dist_m < 0.005:
        return

    p0_px = viewport.world_to_pixel(p0)
    p1_px = viewport.world_to_pixel(p1)
    if p0_px is None or p1_px is None:
        return

    x0, y0 = p0_px
    x1, y1 = p1_px
    if any(math.isnan(v) or math.isinf(v) for v in (x0, y0, x1, y1)):
        return

    dx, dy = x1 - x0, y1 - y0
    screen_len = math.hypot(dx, dy)
    if math.isnan(screen_len) or math.isinf(screen_len) or screen_len < 12.0:
        return

    ux, uy = dx / screen_len, dy / screen_len
    nx, ny = -uy, ux

    cx0, cy0 = x0 + nx * offset_px, y0 + ny * offset_px
    cx1, cy1 = x1 + nx * offset_px, y1 + ny * offset_px

    painter.save()
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        # 1. Linhas de extensão / testemunhas (se houver deslocamento)
        if abs(offset_px) > 1.0:
            pen_ext = QPen(QColor(120, 140, 160, 160), 1.0, Qt.DashLine)
            painter.setPen(pen_ext)
            painter.drawLine(QPointF(x0, y0), QPointF(cx0 + nx * 3.0, cy0 + ny * 3.0))
            painter.drawLine(QPointF(x1, y1), QPointF(cx1 + nx * 3.0, cy1 + ny * 3.0))

        # 2. Linha principal da cota
        painter.setPen(QPen(cota_color, 1.8))
        painter.drawLine(QPointF(cx0, cy0), QPointF(cx1, cy1))

        # 3. Setas indicadoras nas extremidades
        arrow_len = min(8.0, screen_len * 0.22)
        arrow_w = 3.0
        for tip_x, tip_y, sgn in ((cx0, cy0, 1.0), (cx1, cy1, -1.0)):
            ax = tip_x + (ux * sgn) * arrow_len
            ay = tip_y + (uy * sgn) * arrow_len
            painter.drawLine(QPointF(tip_x, tip_y), QPointF(ax + nx * arrow_w, ay + ny * arrow_w))
            painter.drawLine(QPointF(tip_x, tip_y), QPointF(ax - nx * arrow_w, ay - ny * arrow_w))

        # 4. Etiqueta / Badge com valor nítido em mm
        mm_val = int(round(dist_m * 1000.0))
        texto = f"{mm_val} mm"
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw, th = fm.horizontalAdvance(texto), fm.height()

        mid_x, mid_y = (cx0 + cx1) * 0.5, (cy0 + cy1) * 0.5
        pad_x, pad_y = 6, 3
        badge_rect = QRectF(mid_x - tw * 0.5 - pad_x, mid_y - th * 0.5 - pad_y, tw + pad_x * 2, th + pad_y * 2)

        painter.setPen(QPen(cota_color, 1.2))
        painter.setBrush(QColor(24, 28, 36, 220))
        painter.drawRoundedRect(badge_rect, 4.0, 4.0)

        painter.setPen(QColor(255, 255, 255))
        painter.drawText(badge_rect, Qt.AlignCenter, texto)

    finally:
        painter.restore()


class MagneticModuleDragFilter(QObject):
    """Filtro de eventos Qt para movimentação com arraste, aderência magnética e cotas dinâmicas."""

    DRAG_THRESHOLD_PX = 5.0
    SNAP_FLOOR_DISTANCE = 0.15   # 15 cm de atração ao piso
    SNAP_WALL_DISTANCE = 0.25    # 25 cm de atração às paredes

    def __init__(self, viewport, parent: Optional[QObject] = None) -> None:
        super().__init__(parent or viewport)
        self.viewport = viewport

        self._mouse_pressed = False
        self._press_pos: Optional[QPointF] = None
        self._drag_active = False

        self._target_module: Optional[Group] = None
        self._affected_groups: List[Group] = []
        self._start_world_pt: Optional[QVector3D] = None
        self._module_orig_bounds: Optional[Tuple[float, float, float, float, float, float]] = None
        self._active_locked_wall_face = None
        self._press_wall_u: Optional[float] = None
        self._press_wall_z: Optional[float] = None
        self._axis_lock: Optional[str] = None  # None, 'z', 'u', 'x', 'y'
        self._last_event_pos: Optional[QPointF] = None

        # Estado dinâmico de cotas
        self._active_cota_items: List[Tuple[QVector3D, QVector3D, QColor, float]] = []

        # Instala overlay para desenhar as cotas na passagem 2D do Viewport
        self._install_overlay()

    def _install_overlay(self) -> None:
        """Garante que a função de pintura das cotas seja chamada durante a renderização do Viewport."""
        if not hasattr(self.viewport, "_ext_overlays") or self.viewport._ext_overlays is None:
            self.viewport._ext_overlays = []
        if self._draw_cota_overlay not in self.viewport._ext_overlays:
            self.viewport._ext_overlays.append(self._draw_cota_overlay)

        # Conecta a mudanças na cena para atualizar cotas automaticamente
        if hasattr(self.viewport, "sceneVersionChanged"):
            try:
                self.viewport.sceneVersionChanged.connect(self._on_scene_or_selection_changed)
            except Exception:
                pass

    def _get_selected_module(self) -> Optional[Group]:
        """Retorna o módulo TrazoMob atualmente selecionado na cena, se houver."""
        scene = getattr(self.viewport, "scene", None)
        if not scene:
            return None
        sel = getattr(scene, "selection", set())
        for item in sel:
            mod = self._find_top_module(item)
            if mod is not None and self._is_module_group(mod):
                return mod
        return None

    def _refresh_active_cotas(self, target: Optional[Group] = None) -> None:
        """Centraliza o cálculo e atualização das cotas para um módulo ou seleção atual."""
        mod = target or self._get_selected_module()
        if mod and self._is_module_group(mod):
            bounds = get_module_bounds(mod)
            if bounds:
                self._active_cota_items = self._compute_cotas_for_bounds(bounds, exclude_module=mod)
                return
        self._active_cota_items = []

    def _on_scene_or_selection_changed(self, *args) -> None:
        """Atualiza cotas para a seleção atual quando não estiver em drag."""
        if not self._drag_active:
            self._refresh_active_cotas()
            self.viewport.update()

    def _draw_cota_overlay(self, vp, painter: QPainter) -> None:
        """Chamado pelo ciclo de desenho do Viewport (_draw_extension_overlays)."""
        if not self._active_cota_items and not self._drag_active:
            self._refresh_active_cotas()

        for p0, p1, col, offset_px in self._active_cota_items:
            draw_snap_dimension_segment(vp, painter, p0, p1, cota_color=col, offset_px=offset_px)

    def _is_select_tool_active(self) -> bool:
        """Retorna True apenas se a ferramenta ativa no Viewport for a de Seleção (ou nenhuma).
        Quando ferramentas como Move (M), Rotate (Q), Line (L), Tape, etc. estão ativas,
        o filtro magnético NÃO deve interceptar cliques nem desviar a seleção da ferramenta ativa!
        """
        tool = getattr(self.viewport, "active_tool", None)
        if tool is None:
            tool = getattr(self.viewport, "tool", None)
        if tool is None:
            return True
        tname = getattr(tool, "name", "")
        return tname in ("Select", "")

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is not self.viewport:
            return super().eventFilter(watched, event)

        etype = event.type()
        if etype == QEvent.MouseButtonPress and isinstance(event, QMouseEvent):
            if event.button() == Qt.LeftButton:
                if not self._is_select_tool_active():
                    self._mouse_pressed = False
                    self._drag_active = False
                    self._target_module = None
                    return False

                mods = event.modifiers()
                is_multi = bool(mods & (Qt.ControlModifier | Qt.ShiftModifier))

                from .wall_selection import WallSelectionManager
                wall_mgr = WallSelectionManager.get_instance(self.viewport)
                pos_x, pos_y = event.position().x(), event.position().y()
                # 0. Tenta primeiro verificar se clicou numa fonte de luz física (spot, cone, lâmpada ou fita LED)
                from .light_tools import TrazoMobLightVisualizer, _get_document_lights
                light_pick = TrazoMobLightVisualizer.pick_light_or_target(self.viewport, pos_x, pos_y)
                if light_pick is not None:
                    action, light_idx = light_pick
                    TrazoMobLightVisualizer.on_light_clicked(light_pick, self.viewport, click_pos=(pos_x, pos_y))
                    wall_mgr.clear_selection()
                    # Encontra o grupo 3D correspondente na cena para colocar na seleção ativa
                    doc_lights = _get_document_lights(self.viewport)
                    target_grp = None
                    if 0 <= light_idx < len(doc_lights):
                        lt_data = doc_lights[light_idx]
                        sc = getattr(self.viewport, "scene", None)
                        if sc and hasattr(sc, "groups"):
                            for g in sc.groups:
                                ext = getattr(g, "ext", None)
                                if isinstance(ext, dict) and "trazomob_light" in ext:
                                    g_lt = ext["trazomob_light"]
                                    if g_lt.get("pos") == lt_data.get("pos") and g_lt.get("kind") == lt_data.get("kind"):
                                        target_grp = g
                                        break
                    if target_grp is not None and hasattr(self.viewport, "scene"):
                        if hasattr(self.viewport.scene, "select"):
                            self.viewport.scene.select([target_grp], mode="add" if is_multi else "replace")
                        else:
                            self.viewport.scene.selection = {target_grp}
                        if hasattr(self.viewport, "notify_scene_changed"):
                            self.viewport.notify_scene_changed()
                        else:
                            self.viewport.update()
                    # Notifica a barra lateral para abrir a edição da luz diretamente
                    sidebar = getattr(self.viewport, "_trazomob_sidebar", None)
                    if sidebar is not None:
                        if target_grp is not None:
                            sidebar.load_light_group(target_grp)
                        else:
                            sidebar.load_light(light_idx)
                    return True

                # Tenta verificar se clicou numa face de parede
                if wall_mgr.handle_click(pos_x, pos_y):
                    # Se clicou numa parede, seleciona a parede na cena também (se não for multi-seleção de outros tipos)
                    if wall_mgr.selected_wall_face and not is_multi:
                        wall_grp = wall_mgr.selected_wall_face.wall_group
                        if hasattr(self.viewport, "scene"):
                            self.viewport.scene.selection = {wall_grp}
                            self.viewport.update()
                else:
                    # Se clicou num móvel, verifica se ele está encostado em uma parede
                    hit_grp = self.viewport.pick_group(pos_x, pos_y) if hasattr(self.viewport, "pick_group") else None
                    top_mod = self._find_top_module(hit_grp)
                    if top_mod is not None:
                        adj = self._find_adjacent_wall_face(top_mod)
                        if adj is not None:
                            adj_wall, adj_face = adj
                            # Seleciona a parede visualmente no 3D sem roubar o contexto da barra lateral do móvel
                            wall_mgr.set_selected_face(adj_wall, adj_face, notify_sidebar=False)
                        else:
                            wall_mgr.clear_selection()
                    else:
                        # Se clicou no vazio ou num objeto que não é parede nem móvel encostado, limpa
                        face, grp = self.viewport.pick_face_any(pos_x, pos_y) if hasattr(self.viewport, "pick_face_any") else (None, None)
                        if grp is None or not (hasattr(grp, "ext") and isinstance(grp.ext, dict) and "trazomob_wall" in grp.ext):
                            wall_mgr.clear_selection()

                if self._handle_press(event):
                    return False

        elif etype == QEvent.MouseMove and isinstance(event, QMouseEvent):
            if self._mouse_pressed and self._is_select_tool_active():
                if self._handle_move(event):
                    return True  # Intercepta e consome o evento evitando seleção retangular!

        elif etype == QEvent.MouseButtonRelease and isinstance(event, QMouseEvent):
            if event.button() == Qt.LeftButton and (self._mouse_pressed or self._drag_active):
                if not self._is_select_tool_active():
                    self._mouse_pressed = False
                    self._drag_active = False
                    self._target_module = None
                    return False
                if self._handle_release(event):
                    return True

        elif etype == QEvent.KeyPress and (self._mouse_pressed or self._drag_active):
            from PySide6.QtGui import QKeyEvent
            if isinstance(event, QKeyEvent):
                key = event.key()
                # Setas Up / Down: Trava no eixo Vertical (Z)
                if key in (Qt.Key_Up, Qt.Key_Down):
                    if self._axis_lock == "z":
                        self._axis_lock = None
                        if hasattr(self.viewport, "flash_status"):
                            self.viewport.flash_status("🔓 Trava de eixo liberada")
                    else:
                        self._axis_lock = "z"
                        if hasattr(self.viewport, "flash_status"):
                            self.viewport.flash_status("🔒 Eixo Vertical (Z) travado pelas setas [Cima/Baixo]")
                    if self._last_event_pos is not None:
                        self._recompute_from_pos(self._last_event_pos)
                    return True

                # Setas Left / Right: Trava no eixo Horizontal (ao longo da parede / X/Y)
                elif key in (Qt.Key_Left, Qt.Key_Right):
                    if self._axis_lock == "u":
                        self._axis_lock = None
                        if hasattr(self.viewport, "flash_status"):
                            self.viewport.flash_status("🔓 Trava de eixo liberada")
                    else:
                        self._axis_lock = "u"
                        if hasattr(self.viewport, "flash_status"):
                            self.viewport.flash_status("🔒 Eixo Horizontal (ao longo da parede) travado [Esq/Dir]")
                    if self._last_event_pos is not None:
                        self._recompute_from_pos(self._last_event_pos)
                    return True

                elif key == Qt.Key_Escape:
                    if self._axis_lock is not None:
                        self._axis_lock = None
                        if hasattr(self.viewport, "flash_status"):
                            self.viewport.flash_status("🔓 Trava de eixo liberada (Esc)")
                        if self._last_event_pos is not None:
                            self._recompute_from_pos(self._last_event_pos)
                        return True

        return super().eventFilter(watched, event)

    def _is_module_group(self, group: Optional[Group]) -> bool:
        if group is None:
            return False
        return bool(
            hasattr(group, "ext")
            and isinstance(group.ext, dict)
            and ("trazomob_module" in group.ext or "corte_cloud_module" in group.ext or "hellomob_module" in group.ext)
        )

    def _find_top_module(self, group: Optional[Group]) -> Optional[Group]:
        """Encontra o módulo raiz caso o usuário tenha clicado numa peça interna."""
        if group is None:
            return None
        # Se o objeto é uma parede, piso ou está com motion_locked, não deve ser arrastado
        if getattr(group, "motion_locked", False):
            return None
        ext = getattr(group, "ext", None)
        if isinstance(ext, dict):
            if ext.get("motion_locked"):
                return None
            if "trazomob_wall" in ext or "corte_cloud_wall" in ext or "trazomob_floor" in ext:
                return None
        if getattr(group, "layer", "") in ("Parede", "Piso"):
            return None

        if self._is_module_group(group):
            return group

        scene = getattr(self.viewport, "scene", None)
        if scene and hasattr(scene, "groups"):
            for g in scene.groups:
                if self._is_module_group(g):
                    children = getattr(g, "children", []) or []
                    if group in children or any(getattr(c, "owner", None) is g for c in children):
                        return g
        return group if hasattr(group, "mesh") or getattr(group, "xform", None) is not None else None

    def _collect_walls(self) -> List[Group]:
        """Retorna todos os grupos de paredes contínuas presentes na cena."""
        walls = []
        scene = getattr(self.viewport, "scene", None)
        if scene and hasattr(scene, "groups"):
            for g in scene.groups:
                if hasattr(g, "ext") and isinstance(g.ext, dict) and ("trazomob_wall" in g.ext or "corte_cloud_wall" in g.ext):
                    walls.append(g)
        return walls

    def _find_adjacent_wall_face(self, module: Group, tolerance_m: float = 0.08) -> Optional[Tuple[Group, Face]]:
        """Verifica se o móvel está encostado ou rente a alguma face de parede na cena."""
        bounds = get_module_bounds(module)
        if not bounds:
            return None
        min_x, max_x, min_y, max_y, min_z, _ = bounds
        cur_bounds = (min_x, max_x, min_y, max_y, min_z, min_z)
        cur_cx, cur_cy = (min_x + max_x) * 0.5, (min_y + max_y) * 0.5
        cur_center = QVector3D(cur_cx, cur_cy, 0.0)

        walls = self._collect_walls()
        best_match = None
        best_gap = float("inf")

        for wall in walls:
            mesh = getattr(wall, "mesh", None)
            if mesh is None or not getattr(mesh, "faces", None):
                continue
            for face in mesh.faces:
                norm = face.normal()
                if abs(norm.z()) > 0.05:
                    continue
                n_dir = QVector3D(norm.x(), norm.y(), 0.0).normalized()
                f_verts = list(face.vertices)
                if len(f_verts) < 2:
                    continue
                p_ref = QVector3D(f_verts[0].x(), f_verts[0].y(), 0.0)

                # A face precisa estar voltada para o móvel
                if QVector3D.dotProduct(cur_center - p_ref, n_dir) < -0.05:
                    continue

                pts_2d = [QVector3D(v.x(), v.y(), 0.0) for v in f_verts]
                u_dir = QVector3D(-n_dir.y(), n_dir.x(), 0.0).normalized()
                projs = [QVector3D.dotProduct(p, u_dir) for p in pts_2d]
                min_u, max_u = min(projs), max(projs)

                proj_u = QVector3D.dotProduct(cur_center, u_dir)
                if not ((min_u - 0.20) <= proj_u <= (max_u + 0.20)):
                    continue

                cur_min_n = get_bounds_min_projection(cur_bounds, n_dir)
                wall_face_n = QVector3D.dotProduct(p_ref, n_dir)
                dist_gap = abs(cur_min_n - wall_face_n)

                if dist_gap <= tolerance_m and dist_gap < best_gap:
                    best_gap = dist_gap
                    best_match = (wall, face)

        return best_match

    def _handle_press(self, event: QMouseEvent) -> bool:
        pos_x, pos_y = event.position().x(), event.position().y()
        self._press_pos = event.position()
        self._mouse_pressed = True
        self._drag_active = False
        self._current_delta = QVector3D(0, 0, 0)
        self._active_locked_wall_face = None
        self._press_wall_u = None
        self._press_wall_z = None
        self._active_cota_items = []

        hit_group = self.viewport.pick_group(pos_x, pos_y)
        module = self._find_top_module(hit_group)

        if module is None:
            self._target_module = None
            self._affected_groups = []
            self._start_world_pt = None
            return False

        self._target_module = module
        scene = self.viewport.scene
        sel = list(getattr(scene, "selection", []))

        if module in sel and len(sel) > 1:
            self._affected_groups = [g for g in sel if hasattr(g, "mesh") or getattr(g, "xform", None) is not None]
        else:
            self._affected_groups = [module]

        ctx = self.viewport._build_ctx(event)
        if ctx is not None and ctx.world is not None:
            self._start_world_pt = QVector3D(ctx.world)
        else:
            orig, dirc = self.viewport._pixel_to_ray(pos_x, pos_y)
            if orig is not None and dirc is not None and abs(dirc.z()) > 1e-6:
                self._start_world_pt = orig + dirc * (-orig.z() / dirc.z())
            else:
                self._start_world_pt = QVector3D(0, 0, 0)

        # Se o módulo for uma esquadria (porta/janela), usamos sempre os limites totais do conjunto (get_module_bounds),
        # pois portas possuem marcos, guarnições e folhas que não são caixarias de marcenaria.
        is_esq_target = bool(
            hasattr(module, "ext") and isinstance(module.ext, dict) and "trazomob_esquadria" in module.ext
            or getattr(module, "layer", "") == "ESQUADRIAS"
            or "porta" in module.name.lower() or "janela" in module.name.lower()
        )
        if is_esq_target:
            self._module_orig_bounds = get_module_bounds(module)
        else:
            from .module_ribbon import get_module_carcass_bounds
            self._module_orig_bounds = get_module_carcass_bounds(module) or get_module_bounds(module)
        self._auto_rot_deg = 0.0
        self._initial_wall_face = self._find_adjacent_wall_face(module, tolerance_m=0.06)
        if self._module_orig_bounds:
            # Usa o plano Z da base do módulo (ou Z=0 se apoiado no chão) para projeção consistente do arraste horizontal
            base_z = self._module_orig_bounds[4]
            orig, dirc = self.viewport._pixel_to_ray(pos_x, pos_y)
            if orig is not None and dirc is not None and abs(dirc.z()) > 1e-4:
                t_plane = (base_z - orig.z()) / dirc.z()
                if 0.0 < t_plane < 50.0:
                    self._start_world_pt = orig + dirc * t_plane
        return True

    def _handle_move(self, event: QMouseEvent) -> bool:
        if not self._target_module or self._press_pos is None or self._start_world_pt is None:
            return False

        dist_px = math.hypot(
            event.position().x() - self._press_pos.x(),
            event.position().y() - self._press_pos.y(),
        )

        if not self._drag_active:
            if dist_px >= self.DRAG_THRESHOLD_PX:
                self._drag_active = True
                self.viewport._box_active = False
                self.viewport._box_start = None
                self.viewport._box_cur = None

                for g in self._affected_groups:
                    if g not in self.viewport.scene.selection:
                        self.viewport.scene.selection.add(g)

                self.viewport.begin_groups_preview(self._affected_groups)
            else:
                return False

        self._last_event_pos = event.position()
        return self._recompute_from_pos(event.position())

    def _recompute_from_pos(self, pos: QPointF) -> bool:
        if not self._target_module or self._start_world_pt is None:
            return False

        orig, dirc = self.viewport._pixel_to_ray(pos.x(), pos.y())
        if orig is None or dirc is None:
            return True

        plane_z = self._start_world_pt.z() if self._module_orig_bounds else 0.0
        curr_floor_pt = None
        if abs(dirc.z()) > 1e-4:
            t = (plane_z - orig.z()) / dirc.z()
            # Limita a distância máxima de projeção para evitar que o módulo suma no infinito em ângulos rasos
            if 0.0 < t < 35.0:
                curr_floor_pt = orig + dirc * t

        if curr_floor_pt is None:
            dist_ref = max(1.0, min(20.0, (self._start_world_pt - orig).length()))
            curr_floor_pt = orig + dirc * dist_ref
            curr_floor_pt.setZ(plane_z)

        raw_delta = curr_floor_pt - self._start_world_pt
        raw_delta.setZ(0.0)

        # ── CÁLCULO DE ADERÊNCIA MAGNÉTICA (SNAP) ───────────────────────────
        snapped_delta = self._compute_magnetic_snap(raw_delta, orig, dirc)

        self._current_delta = snapped_delta
        if abs(getattr(self, "_auto_rot_deg", 0.0)) > 1e-3 and self._module_orig_bounds:
            from PySide6.QtGui import QMatrix4x4
            from core.history import rotation_matrix
            b = self._module_orig_bounds
            c_orig = QVector3D((b[0] + b[1]) * 0.5, (b[2] + b[3]) * 0.5, (b[4] + b[5]) * 0.5)
            m_rot = rotation_matrix(c_orig, QVector3D(0.0, 0.0, 1.0), self._auto_rot_deg)
            m_tr = QMatrix4x4()
            m_tr.translate(snapped_delta)
            self.viewport.set_groups_preview_matrix(m_tr * m_rot)
        else:
            self.viewport.set_groups_preview_offset(snapped_delta)

        # ── CÁLCULO DAS COTAS EM TEMPO REAL PARA OS OBJETOS MAIS PRÓXIMOS ──
        self._update_snap_cotas(snapped_delta)

        self.viewport.update()
        return True

    def _compute_magnetic_snap(self, raw_delta: QVector3D, ray_orig: QVector3D, ray_dirc: QVector3D) -> QVector3D:
        """Calcula atração magnética ao piso e às paredes circundantes."""
        if not self._module_orig_bounds:
            return raw_delta

        min_x, max_x, min_y, max_y, min_z, max_z = self._module_orig_bounds

        # ── TRATAMENTO ESPECIALIZADO PARA ESQUADRIAS (PORTAS E JANELAS) ──
        # Esquadrias vivem inseridas no plano da parede hospedeira.
        # Seu arraste deve deslizar suavemente e com 100% de liberdade no comprimento da parede (eixo U),
        # mantendo a cota vertical Z estritamente no piso/peitoril e sem sofrer repulsão/penetração normal.
        is_esquadria = False
        if self._target_module and hasattr(self._target_module, "ext") and isinstance(self._target_module.ext, dict):
            if "trazomob_esquadria" in self._target_module.ext:
                is_esquadria = True
            elif getattr(self._target_module, "layer", "") == "ESQUADRIAS":
                is_esquadria = True
            elif "porta" in self._target_module.name.lower() or "janela" in self._target_module.name.lower():
                is_esquadria = True

        walls = self._collect_walls()
        if is_esquadria and walls:
            b = self._module_orig_bounds
            c_esq = QVector3D((b[0] + b[1]) * 0.5, (b[2] + b[3]) * 0.5, 0.0)
            for w in walls:
                w_ext = getattr(w, "ext", {}).get("trazomob_wall", {})
                pts_data = w_ext.get("pontos", [])
                is_closed = w_ext.get("is_closed", False)
                n_pts = len(pts_data)
                n_segs = n_pts if is_closed else max(0, n_pts - 1)
                for seg_i in range(n_segs):
                    p0 = QVector3D(*pts_data[seg_i])
                    p1 = QVector3D(*pts_data[(seg_i + 1) % n_pts])
                    seg_v = p1 - p0
                    seg_len = seg_v.length()
                    if seg_len < 0.05:
                        continue
                    seg_u = seg_v.normalized()
                    seg_n = QVector3D(-seg_u.y(), seg_u.x(), 0.0).normalized()
                    dist_norm = abs(QVector3D.dotProduct(c_esq - p0, seg_n))
                    wall_esp = float(w_ext.get("espessura", 0.15))
                    if dist_norm <= wall_esp + 0.35:
                        proj_u_center = QVector3D.dotProduct(c_esq - p0, seg_u)
                        if -0.50 <= proj_u_center <= seg_len + 0.50:
                            projs = [
                                QVector3D.dotProduct(QVector3D(b[0], b[2], 0.0) - p0, seg_u),
                                QVector3D.dotProduct(QVector3D(b[1], b[2], 0.0) - p0, seg_u),
                                QVector3D.dotProduct(QVector3D(b[0], b[3], 0.0) - p0, seg_u),
                                QVector3D.dotProduct(QVector3D(b[1], b[3], 0.0) - p0, seg_u),
                            ]
                            u_min_cur, u_max_cur = min(projs), max(projs)
                            half_len = (u_max_cur - u_min_cur) * 0.5
                            center_u_cur = (u_min_cur + u_max_cur) * 0.5

                            cur_delta_u = QVector3D.dotProduct(raw_delta, seg_u)
                            target_center_u = center_u_cur + cur_delta_u
                            clamped_center_u = max(half_len, min(seg_len - half_len, target_center_u))
                            final_delta_u = clamped_center_u - center_u_cur

                            final_delta = seg_u * final_delta_u
                            final_delta.setZ(0.0)

                            # Destaca a parede no gerenciador de paredes para feedback visual
                            from .wall_selection import WallSelectionManager
                            wall_mgr = WallSelectionManager.get_instance(self.viewport)
                            if w.mesh and w.mesh.faces:
                                for f in w.mesh.faces:
                                    if abs(f.normal().z()) < 0.05:
                                        if wall_mgr.selected_wall_face is None or wall_mgr.selected_wall_face.wall_group is not w:
                                            wall_mgr.set_selected_face(w, f, notify_sidebar=False)
                                        break
                            return final_delta

        cur_min_x = min_x + raw_delta.x()
        cur_max_x = max_x + raw_delta.x()
        cur_min_y = min_y + raw_delta.y()
        cur_max_y = max_y + raw_delta.y()

        final_dx = raw_delta.x()
        final_dy = raw_delta.y()
        final_dz = raw_delta.z()

        walls = self._collect_walls()
        best_wall_face = None
        best_dist = float("inf")
        locked_candidate = None

        # Parede vinculada atualmente (ou parede em que o móvel já estava encostado ao iniciar o clique)
        current_locked_pair = None
        if self._active_locked_wall_face is not None:
            current_locked_pair = (self._active_locked_wall_face[7], self._active_locked_wall_face[8])
        elif getattr(self, "_initial_wall_face", None) is not None:
            current_locked_pair = self._initial_wall_face

        cur_bounds = (cur_min_x, cur_max_x, cur_min_y, cur_max_y, min_z, min_z)
        cur_cx, cur_cy = (cur_min_x + cur_max_x) * 0.5, (cur_min_y + cur_max_y) * 0.5
        cur_center = QVector3D(cur_cx, cur_cy, 0.0)

        for wall in walls:
            mesh = getattr(wall, "mesh", None)
            if mesh is None or not getattr(mesh, "faces", None):
                continue

            for face in mesh.faces:
                norm = face.normal()
                if abs(norm.z()) > 0.05:
                    continue

                n_dir = QVector3D(norm.x(), norm.y(), 0.0).normalized()
                f_verts = list(face.vertices)
                if len(f_verts) < 2:
                    continue

                # Filtra faces curtas de topo/espessura de parede (< 20cm) para não confundir com paredes reais
                pts_2d = [QVector3D(v.x(), v.y(), 0.0) for v in f_verts]
                u_dir = QVector3D(-n_dir.y(), n_dir.x(), 0.0).normalized()
                projs = [QVector3D.dotProduct(p, u_dir) for p in pts_2d]
                min_u, max_u = min(projs), max(projs)
                if (max_u - min_u) < 0.20:
                    continue

                p_ref = QVector3D(f_verts[0].x(), f_verts[0].y(), 0.0)

                # Projeção da AABB atual do móvel (considerando a dimensão efetiva se girar para esta parede)
                # No construtor (rot_z=0), a frente do móvel (portas) aponta para -Y (0, -1, 0) e o fundo para +Y (0, 1, 0).
                # Para que a frente (portas) aponte para dentro do ambiente (+n_dir), rot_z deve ser atan2(ny, nx) + 90°!
                cand_rot_deg = (round((math.degrees(math.atan2(n_dir.y(), n_dir.x())) + 90.0) / 90.0) * 90.0) % 360.0
                orig_rot_cand = 0.0
                if self._target_module and hasattr(self._target_module, "ext") and isinstance(self._target_module.ext, dict):
                    orig_rot_cand = float(self._target_module.ext.get("trazomob_module", {}).get("rot_z", 0.0) or 0.0) % 360.0
                cand_diff_deg = (cand_rot_deg - orig_rot_cand) % 360.0
                if abs(cand_diff_deg - 90.0) < 1.0 or abs(cand_diff_deg - 270.0) < 1.0:
                    hx_c, hy_c = (cur_max_x - cur_min_x) * 0.5, (cur_max_y - cur_min_y) * 0.5
                    eff_cur_bounds = (cur_cx - hy_c, cur_cx + hy_c, cur_cy - hx_c, cur_cy + hx_c, min_z, min_z)
                else:
                    eff_cur_bounds = cur_bounds

                cur_min_n = get_bounds_min_projection(eff_cur_bounds, n_dir)
                wall_face_n = QVector3D.dotProduct(p_ref, n_dir)
                dist_gap = cur_min_n - wall_face_n
                proj_u = QVector3D.dotProduct(cur_center, u_dir)

                # Raio mirando diretamente na parede (denom < 0 indica que a normal da face aponta em direção à câmera!)
                denom = QVector3D.dotProduct(ray_dirc, n_dir)
                # Ignora a face traseira/externa da parede quando ela está de costas para a câmera (denom > 0.02)
                if denom > 0.02:
                    continue

                ray_hits_wall = False
                hit_wall_z = 0.0
                hit_wall_u = 0.0
                hit_pt_2d = None
                if denom < -1e-4:
                    t_wall = QVector3D.dotProduct(p_ref - ray_orig, n_dir) / denom
                    if 0.0 < t_wall < 30.0:
                        hit_pt = ray_orig + ray_dirc * t_wall
                        hit_u = QVector3D.dotProduct(hit_pt, u_dir)
                        if (min_u - 0.15) <= hit_u <= (max_u + 0.15) and 0.0 <= hit_pt.z() <= 3.5:
                            ray_hits_wall = True
                            hit_wall_z = hit_pt.z()
                            hit_wall_u = hit_u
                            hit_pt_2d = QVector3D(hit_pt.x(), hit_pt.y(), 0.0)

                cand_tuple = (
                    n_dir, u_dir, wall_face_n, cur_min_n,
                    ray_hits_wall, hit_wall_z, hit_wall_u,
                    wall, face, dist_gap, min_u, max_u,
                )

                if current_locked_pair is not None and wall is current_locked_pair[0] and face is current_locked_pair[1]:
                    locked_candidate = cand_tuple

                # Distância normal da caixa à face da parede:
                # Só considera a parede se o móvel estiver próximo da frente da face (-0.30m <= dist_gap < SNAP_WALL_DISTANCE)
                # ou se o raio do cursor estiver apontando diretamente na parede dentro da área útil da face.
                is_near_front = (-0.30 <= dist_gap < self.SNAP_WALL_DISTANCE)
                is_in_bounds_u = ((min_u - 0.15) <= proj_u <= (max_u + 0.15))

                # Se o raio do mouse atinge diretamente a face interna da parede (ray_hits_wall),
                # o ponto na parede (hit_pt_2d) já está dentro dos limites U e Z da parede!
                ray_near_cur = (
                    ray_hits_wall
                    and hit_pt_2d is not None
                    and -2.50 <= dist_gap <= 1.20
                )

                if (is_in_bounds_u and is_near_front) or ray_near_cur:
                    # Quando o cursor aponta diretamente para a face da parede, prioriza a distância da câmera até o impacto
                    rank_dist = abs(dist_gap) * 0.25 if ray_near_cur else abs(dist_gap)
                    if rank_dist < best_dist:
                        best_dist = rank_dist
                        best_wall_face = cand_tuple

        # Se o móvel já estava vinculado a uma parede ativa, ele permanece nela ao deslizar para a esquerda ou direita
        # (evitando que troque de parede sozinho ao encostar no canto da parede perpendicular!).
        # Só permite trocar para outra parede (ou soltar da parede) se o usuário afastar o móvel perpendicularmente
        # da parede ativa (l_dist_gap > SNAP_WALL_DISTANCE, ou > 0.20m quando mirando diretamente na outra parede)!
        if locked_candidate is not None:
            l_n_dir, l_u_dir, l_wall_face_n, l_cur_min_n, l_ray_hits, l_hit_z, l_hit_u, l_wall, l_face, l_dist_gap, l_min_u, l_max_u = locked_candidate
            pointing_at_other_wall = (
                best_wall_face is not None
                and (best_wall_face[7] is not l_wall or best_wall_face[8] is not l_face)
                and best_wall_face[4]  # ray_hits_wall na outra parede
                and l_dist_gap > 0.20  # puxou pelo menos 20cm para fora da parede atual
            )
            if l_dist_gap <= self.SNAP_WALL_DISTANCE and not pointing_at_other_wall:
                best_wall_face = locked_candidate

        # 2. Aplica Aderência Magnética e Bloqueio à Parede Selecionada
        if best_wall_face is not None:
            n_dir, u_dir, wall_face_n, cur_min_n, ray_hits_wall, hit_wall_z, hit_wall_u, matched_wall, matched_face, dist_gap, min_u, max_u = best_wall_face

            # Verifica se o móvel trocou de face de parede durante o arraste!
            prev_locked = self._active_locked_wall_face
            wall_changed = (
                prev_locked is None
                or prev_locked[7] is not matched_wall
                or prev_locked[8] is not matched_face
            )
            self._active_locked_wall_face = best_wall_face

            if wall_changed:
                # Recalcula a referência U/Z na NOVA parede a partir do estado atual para evitar saltos bruscos!
                self._press_wall_u = QVector3D.dotProduct(self._start_world_pt, u_dir)
                self._press_wall_z = self._start_world_pt.z()

            # Auto-rotação inteligente ao encostar em outra parede (portas voltadas para +n_dir, fundo na parede)
            target_rot_deg = (round((math.degrees(math.atan2(n_dir.y(), n_dir.x())) + 90.0) / 90.0) * 90.0) % 360.0
            orig_rot_deg = 0.0
            if self._target_module and hasattr(self._target_module, "ext") and isinstance(self._target_module.ext, dict):
                orig_rot_deg = float(self._target_module.ext.get("trazomob_module", {}).get("rot_z", 0.0) or 0.0) % 360.0
            self._auto_rot_deg = (target_rot_deg - orig_rot_deg) % 360.0

            # Destaca visualmente a face da parede sem roubar a seleção do móvel nem trocar o painel lateral!
            from .wall_selection import WallSelectionManager
            wall_mgr = WallSelectionManager.get_instance(self.viewport)
            if wall_mgr.selected_wall_face is None or wall_mgr.selected_wall_face.wall_group is not matched_wall or wall_mgr.selected_wall_face.face is not matched_face:
                wall_mgr.set_selected_face(matched_wall, matched_face, notify_sidebar=False)

            if self._press_wall_u is None:
                self._press_wall_u = QVector3D.dotProduct(self._start_world_pt, u_dir)
            if self._press_wall_z is None:
                self._press_wall_z = self._start_world_pt.z()

            # Dimensionamento efetivo da caixa após eventual auto-rotação de 90°/270°
            rot_swap = abs(self._auto_rot_deg - 90.0) < 1.0 or abs(self._auto_rot_deg - 270.0) < 1.0
            if rot_swap:
                cx_o, cy_o = (min_x + max_x) * 0.5, (min_y + max_y) * 0.5
                hx_o, hy_o = (max_x - min_x) * 0.5, (max_y - min_y) * 0.5
                eff_bounds = (cx_o - hy_o, cx_o + hy_o, cy_o - hx_o, cy_o + hx_o, min_z, max_z)
            else:
                eff_bounds = (min_x, max_x, min_y, max_y, min_z, max_z)

            cur_mod_corners = [
                (eff_bounds[0], eff_bounds[2]), (eff_bounds[1], eff_bounds[2]),
                (eff_bounds[0], eff_bounds[3]), (eff_bounds[1], eff_bounds[3]),
            ]
            cur_mod_projs_u = [x * u_dir.x() + y * u_dir.y() for x, y in cur_mod_corners]
            cur_mod_center_u = (min(cur_mod_projs_u) + max(cur_mod_projs_u)) * 0.5
            half_len_u = (max(cur_mod_projs_u) - min(cur_mod_projs_u)) * 0.5

            # Usa o deslocamento projetado ao longo de u_dir para continuidade suave entre piso e parede
            orig_center_u = cur_mod_center_u
            cur_delta_u = QVector3D.dotProduct(raw_delta, u_dir)
            if ray_hits_wall:
                raw_dz = hit_wall_z - self._press_wall_z
                candidate_dz = raw_dz if (min_z + raw_dz) > self.SNAP_FLOOR_DISTANCE else -min_z
            else:
                candidate_dz = -min_z

            # Limita o deslizamento U estritamente aos limites físicos da parede [min_u, max_u]
            # descontando a meia-largura do próprio móvel (half_len_u), para que nenhuma das laterais
            # do móvel ultrapasse a parede ou entre dentro das paredes laterais!
            target_center_u = orig_center_u + cur_delta_u
            allowed_min_center_u = min_u + half_len_u
            allowed_max_center_u = max_u - half_len_u
            if allowed_min_center_u <= allowed_max_center_u:
                clamped_center_u = max(allowed_min_center_u, min(allowed_max_center_u, target_center_u))
            else:
                clamped_center_u = (min_u + max_u) * 0.5
            cur_delta_u = clamped_center_u - orig_center_u

            # ── SNAP MAGNÉTICO ÀS LINHAS-GUIA DA RÉGUA DE ALTURA ──
            # Regra de negócio estrita: esquadrias (portas e janelas) NÃO devem sofrer alinhamento
            # ou atração magnética das réguas-guia de marcenaria.
            is_esquadria = False
            if self._target_module and hasattr(self._target_module, "ext") and isinstance(self._target_module.ext, dict):
                if "trazomob_esquadria" in self._target_module.ext:
                    is_esquadria = True
                elif getattr(self._target_module, "layer", "") == "ESQUADRIAS":
                    is_esquadria = True
                elif "porta" in self._target_module.name.lower() or "janela" in self._target_module.name.lower():
                    is_esquadria = True

            from .wall_guides import WallGuideRulerManager
            ruler_mgr = WallGuideRulerManager.get_instance()
            cur_world_bottom_z = min_z + candidate_dz
            cur_world_top_z = max_z + candidate_dz

            # Checa atração magnética na base e no topo do móvel (apenas para módulos de marcenaria)
            snap_bottom = None if is_esquadria else ruler_mgr.snap_to_levels(cur_world_bottom_z, threshold_m=0.10)
            snap_top = None if is_esquadria else ruler_mgr.snap_to_levels(cur_world_top_z, threshold_m=0.10)

            mod_height = max_z - min_z

            # Escolhe o snap adequado:
            chosen_snap = None
            if snap_bottom is not None and snap_top is not None:
                diff_b = getattr(snap_bottom, "diff", abs(cur_world_bottom_z - snap_bottom[0]))
                diff_t = getattr(snap_top, "diff", abs(cur_world_top_z - snap_top[0]))

                # Para móveis altos (balcões/armários de h > 20cm) próximos à região inferior (Z <= 0.40m),
                # a intenção do usuário ao arrastar próximo da base é o rodapé/base, não a bancada superior.
                if mod_height > 0.20 and cur_world_bottom_z <= 0.40:
                    chosen_snap = ("bottom", snap_bottom)
                # Para peças delgadas (tampos, prateleiras, bancadas com h <= 20cm), escolhe o que estiver mais próximo
                elif diff_t < diff_b:
                    chosen_snap = ("top", snap_top)
                else:
                    chosen_snap = ("bottom", snap_bottom)
            elif snap_top is not None:
                chosen_snap = ("top", snap_top)
            elif snap_bottom is not None:
                chosen_snap = ("bottom", snap_bottom)

            if chosen_snap is not None:
                mode, s_info = chosen_snap
                snapped_z = s_info[0]
                guide_name = s_info[1]
                if mode == "top":
                    final_dz = snapped_z - max_z
                else:
                    final_dz = snapped_z - min_z
            else:
                final_dz = candidate_dz

            # ── SNAP MAGNÉTICO CONTÍGUO A OUTROS MÓDULOS NA MESMA PAREDE (EIXO U) ──
            other_modules = []
            scene = getattr(self.viewport, "scene", None)
            if scene and hasattr(scene, "groups"):
                for g in scene.groups:
                    if g is self._target_module or g in self._affected_groups:
                        continue
                    if hasattr(g, "ext") and isinstance(g.ext, dict) and "trazomob_module" in g.ext:
                        other_modules.append(g)

            best_snap_u_offset = None
            min_snap_u_dist = 0.12  # Raio de atração magnética de 12 cm (120 mm)

            for om in other_modules:
                ob = get_module_bounds(om)
                if not ob:
                    continue
                # Verifica se o outro módulo está na mesma parede (distância normal próxima)
                ob_min_n = get_bounds_min_projection(ob, n_dir)
                if abs(ob_min_n - wall_face_n) > 0.15:
                    continue

                # Checa sobreposição ou proximidade no eixo vertical Z
                # Para grudar lateralmente, deve ter alguma compatibilidade vertical
                if (max_z + final_dz) < (ob[4] - 0.20) or (min_z + final_dz) > (ob[5] + 0.20):
                    continue

                # Limites U do módulo vizinho
                o_pts = [
                    (ob[0], ob[2]), (ob[1], ob[2]),
                    (ob[0], ob[3]), (ob[1], ob[3]),
                ]
                o_projs_u = [x * u_dir.x() + y * u_dir.y() for x, y in o_pts]
                o_min_u, o_max_u = min(o_projs_u), max(o_projs_u)

                # Casos de snap contíguo ao longo de U (somente se couber dentro dos limites da parede [min_u, max_u]):
                snap_right_u = (o_max_u + half_len_u) - cur_mod_center_u
                if allowed_min_center_u - 1e-4 <= (orig_center_u + snap_right_u) <= allowed_max_center_u + 1e-4:
                    dist_right = abs(cur_delta_u - snap_right_u)
                    if dist_right < min_snap_u_dist:
                        min_snap_u_dist = dist_right
                        best_snap_u_offset = snap_right_u

                snap_left_u = (o_min_u - half_len_u) - cur_mod_center_u
                if allowed_min_center_u - 1e-4 <= (orig_center_u + snap_left_u) <= allowed_max_center_u + 1e-4:
                    dist_left = abs(cur_delta_u - snap_left_u)
                    if dist_left < min_snap_u_dist:
                        min_snap_u_dist = dist_left
                        best_snap_u_offset = snap_left_u

                # Snap de alinhamento vertical Z com o módulo vizinho (se não houver snap de régua ativo)
                if snap_bottom is None and snap_top is None:
                    if abs((min_z + final_dz) - ob[4]) < 0.08:
                        final_dz = ob[4] - min_z
                    elif abs((max_z + final_dz) - ob[5]) < 0.08:
                        final_dz = ob[5] - max_z

            if best_snap_u_offset is not None:
                cur_delta_u = best_snap_u_offset

            # Reaplica o clamp de segurança após qualquer snap lateral para garantir que o móvel NUNCA ultrapasse os limites da parede!
            if allowed_min_center_u <= allowed_max_center_u:
                cur_delta_u = max(allowed_min_center_u - orig_center_u, min(allowed_max_center_u - orig_center_u, cur_delta_u))

            # ── BLOQUEIO FÍSICO CONTRA PENETRAÇÃO NA PAREDE ──
            orig_min_n = get_bounds_min_projection(eff_bounds, n_dir)
            snap_delta_n = wall_face_n - orig_min_n

            # Componente normal do movimento do mouse
            raw_delta_n = QVector3D.dotProduct(raw_delta, n_dir)

            # Se o cursor do mouse estiver mais afastado para dentro do cômodo do que a parede E não estiver mirando na parede:
            if not ray_hits_wall and raw_delta_n > (snap_delta_n + self.SNAP_WALL_DISTANCE):
                # Puxou claramente para longe da parede, solta o travamento
                self._active_locked_wall_face = None
                self._initial_wall_face = None
                self._auto_rot_deg = 0.0
                final_delta_xy = raw_delta
            else:
                # ── AMARRAÇÃO DIRETA AO PLANO DA PAREDE ──
                final_delta_xy = u_dir * cur_delta_u + n_dir * snap_delta_n

            final_dx = final_delta_xy.x()
            final_dy = final_delta_xy.y()
        else:
            self._active_locked_wall_face = None
            self._auto_rot_deg = 0.0
            final_dz = -min_z
            # Se não estiver preso a uma parede, ainda podemos atrair em X e Y para módulos vizinhos livres
            other_modules = []
            scene = getattr(self.viewport, "scene", None)
            if scene and hasattr(scene, "groups"):
                for g in scene.groups:
                    if g is self._target_module or g in self._affected_groups:
                        continue
                    if hasattr(g, "ext") and isinstance(g.ext, dict) and "trazomob_module" in g.ext:
                        other_modules.append(g)

            cur_min_x_cand = min_x + final_dx
            cur_max_x_cand = max_x + final_dx
            cur_min_y_cand = min_y + final_dy
            cur_max_y_cand = max_y + final_dy
            snap_dist_free = 0.10

            for om in other_modules:
                ob = get_module_bounds(om)
                if not ob:
                    continue
                # Snap X (lateral esquerda/direita)
                if abs(cur_min_x_cand - ob[1]) < snap_dist_free:
                    final_dx = ob[1] - min_x
                elif abs(cur_max_x_cand - ob[0]) < snap_dist_free:
                    final_dx = ob[0] - max_x

                # Snap Y (frente/costas)
                if abs(cur_min_y_cand - ob[3]) < snap_dist_free:
                    final_dy = ob[3] - min_y
                elif abs(cur_max_y_cand - ob[2]) < snap_dist_free:
                    final_dy = ob[2] - max_y

        # ── TRAVA DE EIXOS VIA SETINHAS DO TECLADO (Arrow Keys Lock) ──
        if self._axis_lock == "z":
            # Trava estrita em Z: cancela movimento horizontal (X e Y)
            final_dx = 0.0
            final_dy = 0.0
        elif self._axis_lock == "u":
            # Trava estrita no plano horizontal: cancela movimento vertical (Z)
            final_dz = 0.0

        return QVector3D(final_dx, final_dy, final_dz)

    def _compute_cotas_for_bounds(
        self,
        bounds: Tuple[float, float, float, float, float, float],
        exclude_module: Optional[Group] = None,
        exclude_groups: Optional[List[Group]] = None,
    ) -> List[Tuple[QVector3D, QVector3D, QColor, float]]:
        if any(not math.isfinite(v) for v in bounds):
            return []

        scene = getattr(self.viewport, "scene", None)
        if scene is None:
            return []

        # ── CASO ESPECIAL: COTAS PROJETADAS PARA ESQUADRIAS (PORTAS E JANELAS) ──
        # Projeta a distância exata em mm até a quina esquerda e direita da parede hospedeira
        is_esquadria = False
        target_mod = exclude_module or self._target_module
        if target_mod and hasattr(target_mod, "ext") and isinstance(target_mod.ext, dict):
            if "trazomob_esquadria" in target_mod.ext or getattr(target_mod, "layer", "") == "ESQUADRIAS":
                is_esquadria = True
            elif "porta" in target_mod.name.lower() or "janela" in target_mod.name.lower():
                is_esquadria = True

        if is_esquadria:
            b = bounds
            c_esq = QVector3D((b[0] + b[1]) * 0.5, (b[2] + b[3]) * 0.5, 0.0)
            for g in scene.groups:
                if not (hasattr(g, "ext") and isinstance(g.ext, dict) and "trazomob_wall" in g.ext):
                    continue
                w_ext = g.ext["trazomob_wall"]
                pts_data = w_ext.get("pontos", [])
                is_closed = w_ext.get("is_closed", False)
                n_pts = len(pts_data)
                n_segs = n_pts if is_closed else max(0, n_pts - 1)
                for seg_i in range(n_segs):
                    p0 = QVector3D(*pts_data[seg_i])
                    p1 = QVector3D(*pts_data[(seg_i + 1) % n_pts])
                    seg_v = p1 - p0
                    seg_len = seg_v.length()
                    if seg_len < 0.05:
                        continue
                    seg_u = seg_v.normalized()
                    seg_n = QVector3D(-seg_u.y(), seg_u.x(), 0.0).normalized()
                    dist_norm = abs(QVector3D.dotProduct(c_esq - p0, seg_n))
                    wall_esp = float(w_ext.get("espessura", 0.15))
                    if dist_norm <= wall_esp + 0.35:
                        projs = [
                            QVector3D.dotProduct(QVector3D(b[0], b[2], 0.0) - p0, seg_u),
                            QVector3D.dotProduct(QVector3D(b[1], b[2], 0.0) - p0, seg_u),
                            QVector3D.dotProduct(QVector3D(b[0], b[3], 0.0) - p0, seg_u),
                            QVector3D.dotProduct(QVector3D(b[1], b[3], 0.0) - p0, seg_u),
                        ]
                        u_min = min(projs)
                        u_max = max(projs)
                        z_cota = b[4] + 0.15
                        cota_offset_n = seg_n * (wall_esp * 0.5 + 0.04)

                        esq_cotas = []
                        # Cota Esquerda (da quina esquerda da parede p0 até a lateral da esquadria)
                        p_wall_esq = p0 + cota_offset_n
                        p_wall_esq.setZ(z_cota)
                        p_door_esq = p0 + seg_u * u_min + cota_offset_n
                        p_door_esq.setZ(z_cota)
                        d_esq = (p_door_esq - p_wall_esq).length()
                        if d_esq > 0.01:
                            col_esq = QColor(0, 140, 255) if d_esq > 0.05 else QColor(0, 210, 120)
                            esq_cotas.append((p_wall_esq, p_door_esq, col_esq, 0.0))

                        # Cota Direita (da lateral da esquadria até a quina direita da parede p1)
                        p_door_dir = p0 + seg_u * u_max + cota_offset_n
                        p_door_dir.setZ(z_cota)
                        p_wall_dir = p1 + cota_offset_n
                        p_wall_dir.setZ(z_cota)
                        d_dir = (p_wall_dir - p_door_dir).length()
                        if d_dir > 0.01:
                            col_dir = QColor(0, 140, 255) if d_dir > 0.05 else QColor(0, 210, 120)
                            esq_cotas.append((p_door_dir, p_wall_dir, col_dir, 0.0))

                        # Janelas (peitoril > 0): cotas verticais piso→peitoril e verga→topo da parede
                        z_base = b[4]
                        z_top = b[5]
                        if z_base > 0.05:
                            alt_w = w_ext.get("altura", 2.6)
                            if isinstance(alt_w, (list, tuple)):
                                alt_w = alt_w[seg_i] if seg_i < len(alt_w) else (alt_w[-1] if alt_w else 2.6)
                            try:
                                h_wall = float(alt_w)
                            except (TypeError, ValueError):
                                h_wall = 2.6
                            p_ref = p0 + seg_u * u_min + cota_offset_n - seg_u * 0.10
                            col_v = QColor(0, 140, 255)
                            # Peitoril (piso até a base da janela)
                            p_floor = QVector3D(p_ref.x(), p_ref.y(), 0.0)
                            p_sill = QVector3D(p_ref.x(), p_ref.y(), z_base)
                            esq_cotas.append((p_floor, p_sill, col_v, 0.0))
                            # Altura da janela (base até a verga)
                            p_head = QVector3D(p_ref.x(), p_ref.y(), z_top)
                            esq_cotas.append((p_sill, p_head, QColor(0, 210, 120), 0.0))
                            # Verga até o topo da parede
                            if h_wall > z_top + 0.01:
                                p_wtop = QVector3D(p_ref.x(), p_ref.y(), h_wall)
                                esq_cotas.append((p_head, p_wtop, col_v, 0.0))

                        return esq_cotas

        cur_min_x, cur_max_x, cur_min_y, cur_max_y, cur_min_z, cur_max_z = bounds
        center_x = (cur_min_x + cur_max_x) * 0.5
        center_y = (cur_min_y + cur_max_y) * 0.5
        center_z = (cur_min_z + cur_max_z) * 0.5

        scene = getattr(self.viewport, "scene", None)
        if scene is None:
            return []

        other_modules_bounds: List[Tuple[float, float, float, float, float, float]] = []
        walls_mesh_faces = []

        affected_set = set(exclude_groups or [])
        if exclude_module:
            affected_set.add(exclude_module)
            for c in getattr(exclude_module, "children", []) or []:
                affected_set.add(c)

        for g in getattr(scene, "groups", []):
            if g in affected_set:
                continue
            if hasattr(g, "ext") and isinstance(g.ext, dict):
                if "trazomob_module" in g.ext:
                    b = get_module_bounds(g)
                    if b:
                        other_modules_bounds.append(b)
                elif "trazomob_wall" in g.ext:
                    mesh = getattr(g, "mesh", None)
                    if mesh and getattr(mesh, "faces", None):
                        walls_mesh_faces.extend(mesh.faces)

        # Coleta segmentos de paredes verticais voltados para o ambiente
        wall_segments_2d: List[Tuple[QVector3D, QVector3D, QVector3D]] = []
        for face in walls_mesh_faces:
            n = face.normal()
            if abs(n.z()) > 0.05:
                continue
            verts = list(face.vertices)
            if len(verts) < 2:
                continue
            min_zv = min(v.z() for v in verts)
            bot_verts = [v for v in verts if abs(v.z() - min_zv) < 0.02]
            if len(bot_verts) >= 2:
                wall_segments_2d.append((
                    QVector3D(bot_verts[0].x(), bot_verts[0].y(), 0.0),
                    QVector3D(bot_verts[1].x(), bot_verts[1].y(), 0.0),
                    n,
                ))

        cota_items = []

        # Determina a orientação/face traseira do módulo para posicionar as cotas
        # rente ao fundo (5 a 10 mm avançado da traseira) em vez de no meio do móvel
        rot_deg = 0.0
        if exclude_module and hasattr(exclude_module, "ext") and isinstance(exclude_module.ext, dict):
            cc_dict = exclude_module.ext.get("trazomob_module", {})
            rot_deg = float(cc_dict.get("rot_z", 0.0)) % 360.0

        # Posição de amostragem no plano horizontal:
        # No construtor (rot 0): frente é -Y, fundo é +Y. Avanço de 10 mm para dentro = cur_max_y - 0.010
        # Se rot 180: fundo é -Y -> cur_min_y + 0.010
        # Se rot 90: fundo é -X -> cur_min_x + 0.010
        # Se rot 270: fundo é +X -> cur_max_x - 0.010
        if abs(rot_deg) < 45.0 or abs(rot_deg - 360.0) < 45.0:
            cota_x = center_x
            cota_y = cur_max_y - 0.010
        elif abs(rot_deg - 180.0) < 45.0:
            cota_x = center_x
            cota_y = cur_min_y + 0.010
        elif abs(rot_deg - 90.0) < 45.0:
            cota_x = cur_min_x + 0.010
            cota_y = center_y
        elif abs(rot_deg - 270.0) < 45.0:
            cota_x = cur_max_x - 0.010
            cota_y = center_y
        else:
            cota_x = center_x
            cota_y = cur_max_y - 0.010

        cardinal_rays = [
            ("right", QVector3D(cur_max_x, cota_y, center_z), QVector3D(1, 0, 0)),
            ("left",  QVector3D(cur_min_x, cota_y, center_z), QVector3D(-1, 0, 0)),
            ("front", QVector3D(cota_x, cur_max_y, center_z), QVector3D(0, 1, 0)),
            ("rear",  QVector3D(cota_x, cur_min_y, center_z), QVector3D(0, -1, 0)),
        ]

        for name, p_start, d_ray in cardinal_rays:
            best_t = float("inf")
            best_hit_pt = None

            # 1. Colisão com paredes contínuas
            for wa, wb, wn in wall_segments_2d:
                if QVector3D.dotProduct(d_ray, wn) > -0.01:
                    continue
                v1 = p_start - wa
                v2 = wb - wa
                v3 = QVector3D(-d_ray.y(), d_ray.x(), 0.0)
                dot = QVector3D.dotProduct(v2, v3)
                if abs(dot) > 1e-6:
                    t = (v2.x() * v1.y() - v2.y() * v1.x()) / dot
                    u = (v1.x() * d_ray.y() - v1.y() * d_ray.x()) / -dot
                    if 0.005 < t < best_t and 0.0 <= u <= 1.0:
                        best_t = t
                        best_hit_pt = p_start + d_ray * t

            # 2. Colisão com outros módulos AABB (busca unificada e compacta)
            for om_min_x, om_max_x, om_min_y, om_max_y, om_min_z, om_max_z in other_modules_bounds:
                if cur_max_z < om_min_z or cur_min_z > om_max_z:
                    continue

                t = None
                if name == "right" and om_min_x > cur_max_x and om_min_y <= cota_y <= om_max_y:
                    t = om_min_x - cur_max_x
                elif name == "left" and om_max_x < cur_min_x and om_min_y <= cota_y <= om_max_y:
                    t = cur_min_x - om_max_x
                elif name == "front" and om_min_y > cur_max_y and om_min_x <= cota_x <= om_max_x:
                    t = om_min_y - cur_max_y
                elif name == "rear" and om_max_y < cur_min_y and om_min_x <= cota_x <= om_max_x:
                    t = cur_min_y - om_max_y

                if t is not None and 0.005 < t < best_t:
                    best_t = t
                    best_hit_pt = p_start + d_ray * t

            if best_hit_pt is not None and 0.005 < best_t < 10.0:
                cota_color = QColor(0, 140, 255) if best_t > 0.05 else QColor(0, 210, 120)
                cota_items.append((p_start, best_hit_pt, cota_color, 0.0))

        # Cota Vertical (do piso até a base do módulo) se o módulo estiver elevado
        # Posicionada no plano do fundo para perfeita visibilidade
        if cur_min_z > 0.02:
            p_floor = QVector3D(cota_x, cota_y, 0.0)
            p_base = QVector3D(cota_x, cota_y, cur_min_z)
            cota_items.append((p_floor, p_base, QColor(255, 160, 20), 0.0))

        return cota_items

    def _update_snap_cotas(self, current_delta: QVector3D) -> None:
        """Calcula as cotas dinâmicas nos 4 lados e verticalmente para o objeto mais próximo."""
        if not self._module_orig_bounds:
            self._active_cota_items = []
            return

        min_x, max_x, min_y, max_y, min_z, max_z = self._module_orig_bounds
        cur_bounds = (
            min_x + current_delta.x(),
            max_x + current_delta.x(),
            min_y + current_delta.y(),
            max_y + current_delta.y(),
            min_z + current_delta.z(),
            max_z + current_delta.z(),
        )

        self._active_cota_items = self._compute_cotas_for_bounds(
            cur_bounds,
            exclude_module=self._target_module,
            exclude_groups=self._affected_groups,
        )

    def _handle_release(self, event: QMouseEvent) -> bool:
        self._mouse_pressed = False

        if not self._drag_active:
            target = self._target_module
            self._start_world_pt = None
            self._drag_active = False
            mods = event.modifiers()
            is_multi = bool(mods & (Qt.ControlModifier | Qt.ShiftModifier))
            if target is not None and hasattr(self.viewport, "scene"):
                if is_multi:
                    from tools.select import selection_mode
                    mode = selection_mode(mods)
                    self.viewport.scene.select([target], mode=mode)
                elif target not in self.viewport.scene.selection:
                    self.viewport.scene.selection = {target}
                if hasattr(self.viewport, "notify_scene_changed"):
                    self.viewport.notify_scene_changed()
            self._refresh_active_cotas(target)
            self.viewport.update()
            return False

        self._drag_active = False
        self.viewport.end_groups_preview()

        delta = self._current_delta
        auto_rot_deg = getattr(self, "_auto_rot_deg", 0.0)
        orig_bounds = self._module_orig_bounds
        target_groups = list(self._affected_groups)
        last_target_module = self._target_module

        self._target_module = None
        self._affected_groups = []
        self._start_world_pt = None
        self._current_delta = QVector3D(0, 0, 0)
        self._auto_rot_deg = 0.0
        self._active_locked_wall_face = None
        self._axis_lock = None
        self._last_event_pos = None

        if (delta.length() > 1e-4 or abs(auto_rot_deg) > 1e-3) and target_groups:
            cmds = []
            if abs(auto_rot_deg) > 1e-3 and orig_bounds:
                from .builder import RotateTrazoMobModuleCommand
                for g in target_groups:
                    cmds.append(RotateTrazoMobModuleCommand(g, auto_rot_deg))
            if delta.length() > 1e-4:
                # Expande toda a árvore de grupos (mestre + filhos como marcos, folhas e puxadores)
                all_moving_groups = []
                seen_moving = set()
                def _collect_all(grps):
                    for g in grps:
                        if id(g) in seen_moving:
                            continue
                        seen_moving.add(id(g))
                        if hasattr(g, "mesh") or getattr(g, "xform", None) is not None:
                            all_moving_groups.append(g)
                        _collect_all(getattr(g, "children", []) or [])
                _collect_all(target_groups)

                for g in all_moving_groups:
                    cmds.append(MoveGroupCommand(g, delta))
            if cmds:
                cmd = cmds[0] if len(cmds) == 1 else CompoundCommand(cmds)
                self.viewport.history.execute(cmd)

            # Sincroniza o offset real dos parâmetros do módulo a partir dos bounds da carcaça após o comando
            from .module_ribbon import get_module_carcass_bounds
            for g in target_groups:
                if hasattr(g, "ext") and isinstance(g.ext, dict) and "trazomob_module" in g.ext:
                    cb = get_module_carcass_bounds(g) or get_module_bounds(g)
                    if cb:
                        mod_ext = g.ext["trazomob_module"]
                        unrot_span = mod_ext.get("_unrot_carcass_span")
                        if isinstance(unrot_span, (list, tuple)) and len(unrot_span) == 6:
                            cx_f = (cb[0] + cb[1]) * 0.5
                            cy_f = (cb[2] + cb[3]) * 0.5
                            cz_f = (cb[4] + cb[5]) * 0.5
                            mod_ext["offset"] = (
                                float(cx_f - float(unrot_span[0])),
                                float(cy_f - float(unrot_span[1])),
                                float(cz_f - float(unrot_span[2])),
                            )
                        else:
                            mod_ext["offset"] = (float(cb[0]), float(cb[2]), float(cb[4]))

            # Se algum dos grupos movidos for uma luminária, sincroniza as coordenadas reais da luz
            if any(hasattr(g, "ext") and isinstance(g.ext, dict) and "trazomob_light" in g.ext for g in target_groups):
                try:
                    from .light_tools import sync_scene_lights_to_document
                    sync_scene_lights_to_document(self.viewport)
                except Exception:
                    pass

            # Se algum dos grupos movidos for uma esquadria, atualiza os recortes de parede
            if any(
                hasattr(g, "ext") and isinstance(g.ext, dict) and (
                    "trazomob_esquadria" in g.ext or getattr(g, "layer", "") == "ESQUADRIAS"
                    or "porta" in g.name.lower() or "janela" in g.name.lower()
                )
                for g in target_groups
            ):
                try:
                    from .wall_mesh_builder import WallMeshBuilder
                    if hasattr(self.viewport, "scene"):
                        WallMeshBuilder.sync_scene_wall_openings(self.viewport.scene)
                except Exception:
                    pass

            if last_target_module is not None and hasattr(self.viewport, "scene"):
                self.viewport.scene.selection = {last_target_module}

            if hasattr(self.viewport, "notify_scene_changed"):
                self.viewport.notify_scene_changed()
            if hasattr(self.viewport, "flash_status"):
                dx_mm = int(round(delta.x() * 1000.0))
                dy_mm = int(round(delta.y() * 1000.0))
                dz_mm = int(round(delta.z() * 1000.0))
                self.viewport.flash_status(f"Módulo movido: ΔX={dx_mm}mm, ΔY={dy_mm}mm, ΔZ={dz_mm}mm (Snap Magnético)")

        # Recalcula e mantém as cotas ativas na posição final do módulo selecionado
        self._refresh_active_cotas(last_target_module)

        # Se o módulo finalizou o movimento encostado na parede, mantém a parede selecionada visualmente
        if last_target_module is not None:
            from .wall_selection import WallSelectionManager
            wall_mgr = WallSelectionManager.get_instance(self.viewport)
            adj = self._find_adjacent_wall_face(last_target_module)
            if adj is not None:
                adj_wall, adj_face = adj
                wall_mgr.set_selected_face(adj_wall, adj_face, notify_sidebar=False)

        self.viewport.update()
        return True
